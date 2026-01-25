"""Tests for the stdlib path module."""

import pytest


def test_stdlib_path_helpers(run_tiny_source, monkeypatch):
    """Test stdlib.path helpers across separators and extensions."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = run_tiny_source(
        """
        import stdlib.path;

        print(path.normalize("C:\\Users\\me\\..\\bin"));

        def parts = new["/var", "log", "app"];
        print(path.join(parts));
        def _cleanup_parts = delete(parts);

        def split_parts = path.split("/var/log");
        print(Collections.len(split_parts));
        print(heap_get(split_parts, 0));
        print(heap_get(split_parts, 1));
        print(heap_get(split_parts, 2));
        def _cleanup_split = delete(split_parts);

        print(path.basename("/var/log/app.txt"));
        print(path.dirname("/var/log/app.txt"));
        print(path.extension("/var/log/app.txt"));
        print(path.extension("archive.tar.gz"));
        print(path.extension(".env"));

        print(path.is_absolute("/var/log"));
        print(path.is_absolute("C:\\Temp"));
        print(path.is_absolute("relative/path"));
        """,
    )

    assert (
        out
        == "C:/Users/bin\n/var/log/app\n3\n\nvar\nlog\napp.txt\n/var/log\ntxt\ngz\n\ntrue\ntrue\nfalse\n"
    )


def test_stdlib_path_join_rejects_invalid_inputs(run_tiny_source, monkeypatch):
    """Test stdlib.path join rejects invalid inputs."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    with pytest.raises(Exception, match=r"collections operation expects a heap pointer or list"):
        run_tiny_source(
            """
            import stdlib.path;
            print(path.join("not-a-list"));
            """,
        )
