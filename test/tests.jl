using Test

include("../tiny_lang.jl")  # lädt module TinyLanguage

function run_tiny(src::String)
    # kompiliert TinyLanguage-Quelltext zu einem Julia-String
    julia_code = TinyLanguage.compile_to_julia(src)

    # generierten Julia-Code in anonymes Modul laden
    mod = Module()
    Base.include_string(mod, julia_code)

    # __tiny_run__ aufrufen (world-age-sicher)
    f = getfield(mod, :__tiny_run__)
    return Base.invokelatest(f)
end

# Compile-Error erwarten
function expect_compile_error(src::String, pat::AbstractString)
    try
        TinyLanguage.compile_to_julia(src)
        @test false
    catch e
        got = sprint(showerror, e)
        @test occursin(Regex(pat), got)
    end
end

# ---------------- Tests ----------------

@testset "Lexer basics (define)" begin
    out = run_tiny("""
        define a = 7;
        print(a);
    """)
    @test out == "7\n"
end

@testset "Arithmetic & print with define" begin
    out = run_tiny("""
        define a = 7 + 5 * 2;
        print(a);
    """)
    @test out == "17\n"
end

@testset "Comparisons" begin
    out = run_tiny("""
        print(3 > 2);
        print(3 >= 3);
        print(2 < 1);
        print(2 <= 2);
        print(3 == 3);
    """)
    @test out == "true\ntrue\nfalse\ntrue\ntrue\n"
end

@testset "Function + return + call" begin
    out = run_tiny("""
        fn add(a, b) {
            print(a);     // beide Parameter werden verwendet
            return a + b;
        }
        define r = add(10, 5);
        print(r);
    """)
    @test out == "10\n15\n"
end

@testset "While + If/Else" begin
    out = run_tiny("""
        define i = 0;
        define s = 0;
        while (i < 4) {
            if (i == 2) {
                define t = 100;
                print(t);
            } else {
                define u = 1;
                print(u);
            }
            s = s + 1;
            i = i + 1;
        }
        print(s);
    """)
    @test out == "1\n1\n100\n1\n4\n"
end

@testset "Heap new/delete + get/set + tag (must-use)" begin
    out = run_tiny("""
        define p = new(3);

        { e } = heap_set(p, 0, 11); print(e.code);
        { e } = heap_set(p, 1, 22); print(e.code);
        { e } = heap_set(p, 2, 33); print(e.code);

        print(heap_get(p, 0));
        print(heap_get(p, 1));
        print(heap_get(p, 2));

        { e } = tag(p, Arr); print(e.code);

        { e } = delete(p);   print(e.code);
    """)
    @test out == "0\n0\n0\n11\n22\n33\n0\n0\n"
end

@testset "Pointer of arrays (flat + nested)" begin
    out = run_tiny("""
        // flat init
        define p = new(3);
        { e } = heap_set(p, 0, 11); print(e.code);
        { e } = heap_set(p, 1, 22); print(e.code);
        { e } = heap_set(p, 2, 33); print(e.code);
        print(heap_get(p, 0));
        print(heap_get(p, 1));
        print(heap_get(p, 2));

        // literal init
        define q = new[7, 8, 9];
        print(heap_get(q, 0));
        print(heap_get(q, 1));
        print(heap_get(q, 2));

        // nested: array of pointers
        define a = new[1, 2, 3];
        define b = new[4, 5];

        define r = new(2);
        { e } = heap_set(r, 0, a); print(e.code);
        { e } = heap_set(r, 1, b); print(e.code);

        print(heap_get(heap_get(r, 0), 2)); // a[2] == 3
        print(heap_get(heap_get(r, 1), 1)); // b[1] == 5

        { e } = delete(a); print(e.code);
        { e } = delete(b); print(e.code);
        { e } = delete(p); print(e.code);
        { e } = delete(q); print(e.code);
        { e } = delete(r); print(e.code);
    """)
    @test out == "0\n0\n0\n11\n22\n33\n7\n8\n9\n0\n0\n3\n5\n0\n0\n0\n0\n0\n"
end

# ---------- NEGATIVE: MUST-USE ----------

@testset "MUST-USE: ungenutzter Funktionsparameter" begin
    src = """
    fn f(a, b) {
        print(a);
        return a;
    }
    """
    expect_compile_error(src, "unused parameter\\(s\\) in function f: b")
end

@testset "MUST-USE: ungenutzte lokale Bindung (Top-Level)" begin
    src = """
    define x = 1;
    print(42);
    """
    expect_compile_error(src, "unused local binding\\(s\\): x")
end

@testset "MUST-USE: ungenutzte lokale Bindung (in Funktion)" begin
    src = """
    fn g(a) {
        define t = 123;
        print(a);
        return a;
    }
    """
    expect_compile_error(src, "unused local binding\\(s\\): t")
end

@testset "MUST-USE: bare call verboten" begin
    src = """
    fn h() { return 1; }
    h();
    """
    expect_compile_error(src, "bare call statements are not allowed")
end

@testset "MUST-USE: Destrukturierung – alle Felder nutzen" begin
    src = """
    fn make() { return { p: 1, e: 0 }; }
    { p, e } = make();
    print(p);
    """
    expect_compile_error(src, "unused local binding\\(s\\): e")
end

@testset "OK: Destrukturierung – beide Werte" begin
    src = """
    fn make() { return { p: 1, e: 0 }; }
    { p, e } = make();
    print(p);
    print(e);
    """
    out = run_tiny(src)
    @test out == "1\n0\n"
end

@testset "OK: Funktionsaufruf als Argument" begin
    src = """
    fn one() { return 1; }
    print(one());
    """
    out = run_tiny(src)
    @test out == "1\n"
end

@testset "TypeDef: simple record type" begin
    src = """
    type Error {
        code: number;
        msg: string;
    }

    fn make_error(c, m) {
        return { code: c, msg: m };
    }

    print(__type_field_type("Error", "code"));
    print(__type_field_type("Error", "msg"));
    """
    out = run_tiny(src)
    @test out == "number\nstring\n"
end
