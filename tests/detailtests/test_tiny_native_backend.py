import pathlib

from tiny_language import compile_and_run

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
AST_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_ast.tiny").read_text(encoding="utf-8")
NATIVE_IR_SRC = (PROJECT_ROOT / "src_tiny" / "native_ir.tiny").read_text(encoding="utf-8")
CODEGEN_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_codegen_native.tiny").read_text(encoding="utf-8")
NATIVE_VM_SRC = (PROJECT_ROOT / "src_tiny" / "native_vm.tiny").read_text(encoding="utf-8")


def test_tiny_native_backend_smoke() -> None:
    program = "\n\n".join(
        [
            AST_SRC,
            NATIVE_IR_SRC,
            CODEGEN_SRC,
            NATIVE_VM_SRC,
            """
define stmts = new[
    Let("a", Num("3", Null, Null), Null, Null, Null),
    Print(new[Var("a", Null, Null)], Null, Null)
];

define codegen = NativeCodeGenerator();
define program = codegen.compile_program(stmts);
define vm = NativeVM();
define out = vm.run(program);
print(out);
""",
        ]
    )

    output = compile_and_run(program).strip()

    assert output == "3"
