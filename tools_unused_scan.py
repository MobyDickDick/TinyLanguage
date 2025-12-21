import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple

Root = Path(__file__).parent

class ModuleData:
    def __init__(self, path: Path):
        self.path = path
        self.definitions: List[Tuple[str, str, int]] = []
        self.imports: List[Tuple[str, int]] = []
        self.assigned: List[Tuple[str, int]] = []
        self.used_names: Set[str] = set()
        self.used_attrs: Set[str] = set()
        self.explicit_exports: Set[str] = set()

    def record_definition(self, kind: str, name: str, lineno: int) -> None:
        self.definitions.append((kind, name, lineno))

    def record_import(self, name: str, lineno: int) -> None:
        self.imports.append((name, lineno))

    def record_assignment(self, name: str, lineno: int) -> None:
        self.assigned.append((name, lineno))

    def mark_used(self, name: str) -> None:
        self.used_names.add(name)

    def mark_attr(self, attr: str) -> None:
        self.used_attrs.add(attr)

    @property
    def exported(self) -> Set[str]:
        return self.explicit_exports


def parse_file(path: Path) -> ModuleData:
    data = ModuleData(path)
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return data

    class DefinitionVisitor(ast.NodeVisitor):
        def __init__(self):
            self.level = 0

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if self.level == 0:
                data.record_definition("function", node.name, node.lineno)
            self.level += 1
            self.generic_visit(node)
            self.level -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if self.level == 0:
                data.record_definition("async function", node.name, node.lineno)
            self.level += 1
            self.generic_visit(node)
            self.level -= 1

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if self.level == 0:
                data.record_definition("class", node.name, node.lineno)
            self.level += 1
            self.generic_visit(node)
            self.level -= 1

        def visit_Assign(self, node: ast.Assign) -> None:
            if self.level == 0:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        data.record_assignment(target.id, target.lineno)
            if any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
            ):
                exports = []
                if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                    exports = [elt for elt in node.value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
                if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, (ast.Add, ast.BitOr)):
                    parts = []
                    for part in [node.value.left, node.value.right]:
                        if isinstance(part, (ast.List, ast.Tuple, ast.Set)):
                            parts.extend(
                                elt for elt in part.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                            )
                    exports = parts
                data.explicit_exports.update(elt.value for elt in exports)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if self.level == 0 and isinstance(node.target, ast.Name):
                data.record_assignment(node.target.id, node.lineno)
            if isinstance(node.target, ast.Name) and node.target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                data.explicit_exports.update(
                    elt.value for elt in node.value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                )
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                data.record_import(alias.asname or alias.name.split(".")[0], node.lineno)
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.module == "__future__":
                return
            for alias in node.names:
                if alias.name == "*":
                    continue
                data.record_import(alias.asname or alias.name, node.lineno)
            self.generic_visit(node)

    class UsageVisitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, (ast.Load, ast.Del)):
                data.mark_used(node.id)
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            data.mark_attr(node.attr)
            self.generic_visit(node)

        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str) and node.value.isidentifier():
                data.mark_used(node.value)

    DefinitionVisitor().visit(tree)
    UsageVisitor().visit(tree)
    data.used_names.update(data.exported)
    if "tests" in path.parts:
        for kind, name, _ in data.definitions:
            if name.startswith("test_"):
                data.mark_used(name)
    return data


def scan(paths: List[Path]) -> Tuple[Dict[Path, ModuleData], Set[str], Set[str]]:
    modules: Dict[Path, ModuleData] = {}
    used_names: Set[str] = set()
    used_attrs: Set[str] = set()

    for path in paths:
        if path.suffix != ".py":
            continue
        data = parse_file(path)
        modules[path] = data
        used_names.update(data.used_names)
        used_attrs.update(data.used_attrs)
    return modules, used_names, used_attrs


def find_python_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.py") if ".venv" not in p.parts and "__pycache__" not in p.parts]


def main() -> None:
    targets = [Root / "src", Root / "examples", Root / "tests"]
    files: List[Path] = []
    for target in targets:
        if target.exists():
            files.extend(find_python_files(target))
    modules, used_names, used_attrs = scan(files)

    unused_defs: List[Tuple[str, str, Path, int]] = []
    unused_imports: List[Tuple[str, Path, int]] = []
    unused_assignments: List[Tuple[str, Path, int]] = []

    for path, data in modules.items():
        # imports used per module only
        local_used = data.used_names | data.used_attrs
        for name, lineno in data.imports:
            if name not in local_used:
                unused_imports.append((name, path, lineno))
        for kind, name, lineno in data.definitions:
            if name not in used_names and name not in used_attrs:
                unused_defs.append((kind, name, path, lineno))
        for name, lineno in data.assigned:
            if name not in used_names and name not in used_attrs:
                unused_assignments.append((name, path, lineno))

    print("Unused definitions:")
    for kind, name, path, lineno in sorted(unused_defs, key=lambda x: (str(x[2]), x[3], x[1])):
        print(f"{path}:{lineno}: {kind} '{name}' appears unused")

    print("\nUnused imports:")
    for name, path, lineno in sorted(unused_imports, key=lambda x: (str(x[1]), x[2], x[0])):
        print(f"{path}:{lineno}: import '{name}' appears unused")

    print("\nUnused assignments:")
    for name, path, lineno in sorted(unused_assignments, key=lambda x: (str(x[1]), x[2], x[0])):
        print(f"{path}:{lineno}: assignment to '{name}' appears unused")


if __name__ == "__main__":
    main()
