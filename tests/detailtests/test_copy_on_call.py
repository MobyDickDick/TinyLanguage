"""Tests for copy-on-call semantics in TinyLanguage."""

import pytest

from tiny_language import TinyLangError, compile_and_run

from tests.utils import execute_tiny_program


def test_mutable_parameter_is_copied():
    """Ordinary calls isolate writes to a mutable argument."""
    source = """
    fn bump(buf) {
        def ignored1 = heap_set(buf, 0, 99);
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 1);
    def _unused3 = bump(data);
    print(heap_get(data, 0));
    """

    output = compile_and_run(source, copy_on_call=True)

    assert output.strip() == "1"


def test_returned_parameter_is_a_copy():
    """Returning an actual alias keeps the original isolated."""
    source = """
    fn passthrough(buf) {
        def ignored1 = heap_set(buf, 0, 42);
        return buf;
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 7);
    def alias = passthrough(data);
    print(heap_get(data, 0));
    print(heap_get(alias, 0));
    def ignored2 = heap_set(alias, 0, 101);
    print(heap_get(data, 0));
    print(heap_get(alias, 0));
    """

    output = compile_and_run(source, copy_on_call=True)

    assert output.strip().splitlines() == ["7", "42", "7", "101"]


def test_legacy_behavior_when_copy_on_call_disabled():
    """Verify legacy in-place mutation when copy-on-call is disabled."""
    source = """
    fn bump(buf) {
        def ignored1 = heap_set(buf, 0, 99);
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 1);
    def _unused11 = bump(data);
    print(heap_get(data, 0));
    """

    output = compile_and_run(source, copy_on_call=False)

    assert output.strip() == "99"


def test_mutating_protected_argument_raises():
    """Ensure mutating a protected alias raises a TinyLangError."""
    source = """
    def shared = new(1);

    fn mutate_through_alias(p) {
        if (p == p) {
            def ignored1 = heap_set(shared, 0, 5);
        }
    }

    def _unused14 = mutate_through_alias(shared);
    """

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source, copy_on_call=True)

    assert "protected parameter p" in str(excinfo.value)


@pytest.mark.parametrize("args,env", [
    (["--copy-on-call"], {}), ([], {"TINYLANG_COPY_ON_CALL": "1"}),
])
def test_cli_flag_and_environment_enable_copy_on_call(args, env):
    """Both supported opt-in paths use the scalar-return isolation contract."""
    source = """
    fn bump(buf) {
        def ignored1 = heap_set(buf, 0, 99);
        return len(buf);
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 1);
    def size = bump(data);
    print(heap_get(data, 0));
    print(size);
    """

    result = execute_tiny_program(source, args=args, env=env)

    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == ["1", "1"]
    assert result.stderr == ""


@pytest.mark.parametrize("tail", [
    "return len(buf);",
    "return heap_get(buf, 0);",
    "return len(buf) + 100;",
    "if (len(buf) > 0) { return len(buf); } return 0;",
    "if (false) { return buf; } return 100;",
    "switch (len(buf)) { case 1: { return 100; } default: { return 101; } }",
])
def test_return_expressions_do_not_grant_mutation_permission(tail):
    """Scalar, conditional and unreachable returns all preserve caller data."""
    source = f"""
    fn bump(buf) {{
        def ignored = heap_set(buf, 0, 99);
        {tail}
    }}
    def data = new[7];
    def ignored_result = bump(data);
    print(heap_get(data, 0));
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "7\n"


@pytest.mark.parametrize("tail", [
    "return buf;",
    "def alias = buf; return alias;",
    "if (len(buf) > 0) { return buf; } return identity(buf);",
    "return identity(buf);",
])
def test_alias_returns_remain_isolated(tail):
    """Mutating through a local or returned alias preserves caller data."""
    source = f"""
    fn identity(value) {{ return value; }}
    fn bump(buf) {{
        def local_alias = buf;
        def ignored = heap_set(local_alias, 0, 99);
        {tail}
    }}
    def data = new[7];
    def result = bump(data);
    print(heap_get(data, 0));
    print(heap_get(result, 0));
    def ignored = heap_set(result, 0, 101);
    print(heap_get(data, 0));
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "7\n99\n7\n"


def test_caller_explicitly_adopts_returned_copy():
    """Assignment is the explicit point where a caller adopts changed data."""
    source = """
    fn bump(buf) { def ignored = heap_set(buf, 0, 99); return buf; }
    def data = new[7];
    def updated = bump(data);
    def ignored = delete(data);
    data = updated;
    print(heap_get(data, 0));
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "99\n"


def test_unreachable_return_is_rejected_without_running_mutation():
    """The existing unreachable-code diagnostic still precedes execution."""
    source = """
    fn bump(buf) {
        def ignored = heap_set(buf, 0, 99);
        return 100;
        return buf;
    }
    def data = new[7];
    print(bump(data));
    """
    with pytest.raises(TinyLangError) as error:
        compile_and_run(source, copy_on_call=True, stream_output=False)
    assert error.value.code == "E013"


def test_nested_calls_copy_at_each_boundary():
    """Mutations in a nested call require explicit adoption by the outer call."""
    source = """
    fn inner(buf) { def ignored = heap_set(buf, 0, 99); return buf; }
    fn outer(buf) {
        def changed = inner(buf);
        print(heap_get(buf, 0));
        return changed;
    }
    def original = new[7];
    def result = outer(original);
    print(heap_get(original, 0));
    print(heap_get(result, 0));
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "7\n7\n99\n"


def test_returned_container_holds_aliases_to_the_copy():
    """An alias nested in a returned container never reaches caller storage."""
    source = """
    fn wrap(buf) {
        def ignored = heap_set(buf, 0, 99);
        return new[buf, buf];
    }
    def data = new[7];
    def result = wrap(data);
    def left = heap_get(result, 0);
    def right = heap_get(result, 1);
    print(heap_get(data, 0));
    print(heap_get(right, 0));
    def ignored = heap_set(left, 0, 101);
    print(heap_get(right, 0));
    print(heap_get(data, 0));
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "7\n99\n101\n7\n"


def test_repeated_arguments_share_one_isolated_heap_graph():
    """Two parameters alias each other when their caller arguments alias."""
    source = """
    fn change(left, right) {
        def ignored = heap_set(left, 0, 99);
        print(heap_get(right, 0));
        return right;
    }
    def original = new[7];
    def result = change(original, original);
    print(heap_get(original, 0));
    print(heap_get(result, 0));
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "99\n7\n99\n"


def test_method_receiver_is_shared_and_explicit_arguments_are_copied():
    """Method syntax retains receiver identity without exempting its arguments."""
    source = """
    class Counter {
        value: number;
        fn bump(self) {
            self.value = 101;
            return self;
        }
        fn change(self, buf) {
            def ignored = heap_set(buf, 0, 99);
            return buf;
        }
    }
    def counter = new Counter { value: 100; };
    def data = new[7];
    def ignored_counter = counter.bump();
    def result = counter.change(data);
    print(counter.value);
    print(heap_get(data, 0));
    print(heap_get(result, 0));
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "101\n7\n99\n"


def test_method_mutates_local_copy_of_object_argument():
    """Calling a method on a copied argument cannot modify its original."""
    source = """
    class Counter {
        value: number;
        fn bump(self) { self.value = 101; return self; }
    }
    fn change(counter) { return counter.bump(); }
    def original = new Counter { value: 100; };
    def result = change(original);
    print(original.value);
    print(result.value);
    """
    assert compile_and_run(source, copy_on_call=True, stream_output=False) == "100\n101\n"


def test_global_method_receiver_cannot_bypass_argument_protection():
    """The shared receiver exception respects an enclosing protected graph."""
    source = """
    class Counter {
        value: number;
        fn bump(self) { self.value = 101; return self; }
    }
    fn change(counter) {
        def ignored = counter.value;
        return original.bump();
    }
    def original = new Counter { value: 100; };
    def result = change(original);
    print(result.value);
    """
    with pytest.raises(TinyLangError, match="protected parameter counter"):
        compile_and_run(source, copy_on_call=True, stream_output=False)


@pytest.mark.parametrize("operation", [
    "heap_set(shared, 0, 99)", "delete(shared)", "tag(shared, \"changed\")",
    "mutate(shared)",
])
def test_actual_alias_return_does_not_authorize_global_alias_writes(operation):
    """Even a real return alias cannot authorize writes to the original graph."""
    source = f"""
    def shared = new[7];
    fn mutate(_value) {{ return heap_set(shared, 0, 99); }}
    fn change(buf) {{
        def ignored = {operation};
        return buf;
    }}
    def result = change(shared);
    print(result);
    """
    with pytest.raises(TinyLangError, match="protected parameter"):
        compile_and_run(source, copy_on_call=True, stream_output=False)


@pytest.mark.parametrize("kind", ["list", "dict", "class", "heap", "mixed"])
def test_copy_preserves_shared_and_cyclic_graphs(kind):
    """Identity assertions provide a graph oracle independent of return analysis."""
    from tiny_language import Environment, Param, Runtime, SourcePos

    runtime = Runtime("")
    runtime.copy_on_call = True
    allocate = runtime._Runtime__new
    if kind == "heap":
        shared = allocate(1)
        runtime.heap_set(shared, 0, shared)
        root = allocate(2)
        runtime.heap_set(root, 0, shared)
        runtime.heap_set(root, 1, shared)
    else:
        shared = []
        shared.append(shared)
        if kind == "list":
            root = [shared, shared]
        elif kind == "dict":
            root = {"left": shared, "right": shared}
        elif kind == "class":
            fields = {"left": shared, "right": shared}
            root = {"__tag__": "Box", "__fields__": {"Box": fields}, "alias": fields}
        else:
            root = allocate(1)
            shared.append(root)
            runtime.heap_set(root, 0, shared)

    env = Environment(parent=None, runtime=runtime)
    bindings = runtime._bind_parameters_to_env(
        [Param("root"), Param("shared")], [root, shared], env,
        pos=SourcePos.origin(), type_label="graph test",
    )
    copied = env.get("root")
    copied_shared = env.get("shared")
    if kind == "heap":
        assert copied != root and copied_shared != shared
        assert runtime.heap_get(copied, 0) == copied_shared
        assert runtime.heap_get(copied, 1) == copied_shared
        assert runtime.heap_get(copied_shared, 0) == copied_shared
        assert len(runtime.heap) == 4
    else:
        assert copied is not root and copied_shared is not shared
        assert copied_shared[0] is copied_shared
        if kind == "list":
            assert copied[0] is copied[1] is copied_shared
        elif kind == "dict":
            assert copied["left"] is copied["right"] is copied_shared
        elif kind == "class":
            assert copied["__fields__"]["Box"] is copied["alias"]
            assert copied["alias"]["left"] is copied["alias"]["right"] is copied_shared
        else:
            assert copied != root
            assert runtime.heap_get(copied, 0) is copied_shared
            assert copied_shared[1] == copied
    assert bindings


def test_legacy_ast_escape_metadata_cannot_bypass_copying():
    """Externally supplied and old port ASTs cannot restore inferred permission."""
    from tiny_language import Fn, Param, Return, Runtime, Var

    runtime = Runtime("")
    runtime.copy_on_call = True
    fn = Fn("identity", [Param("value")], [Return(Var("value"))],
            return_param_names={"value"})
    original = ["original"]
    result = runtime._invoke_function(fn, [original])
    assert result == original and result is not original


def test_documented_contract_and_migration_execute_verbatim():
    """Published scalar and alias examples must match the chosen contract."""
    import re
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "docs/copy_on_call_contract.md").read_text(encoding="utf-8")
    examples = re.findall(r"```tiny\n(.*?)```", text, re.DOTALL)
    assert len(examples) == 2
    for source, expected in zip(examples, ["7\n1\n", "7\n99\n"]):
        assert compile_and_run(source, copy_on_call=True, stream_output=False) == expected
