module TinyLanguage

# tiny_lang.jl — Mini-Sprache (Lexer → Parser/IR → Linter → Julia-Codegen)
# Features:
#   - define, Zuweisung, print, if/else, while, fn, return, operator-Overloads
#   - Arrays: new(n) und new[items...] (0-basierte Indizes für heap_*)
#   - Strings mit Escapes \" \\ \n \r \t
#   - Struct-Literale: { field: expr, ... } (+ Kurzschema number/string/bool/any)
#   - Feldzugriff: obj.field
#   - Destrukturierung zu Record: {a, b} = expr;
#   - type-Definitionen: type Name { field: Type; ... }
#   - MUST-USE-Linter: alle Funktionsparameter + lokale Bindungen müssen verwendet werden
#   - Bare call Statements sind verboten (jede Funktion liefert etwas; wenn ignoriert → Fehler)

export compile_to_julia

########################
# Tracing (optional)
########################

const TRACE_LEX   = Ref{Bool}(false)
const TRACE_PARSE = Ref{Bool}(false)

########################
# Lexer
########################

struct Token
    kind::Symbol   # :NAME, :NUMBER, :STRING, :OP, :SYMBOL, :KW, :EOF
    text::String
    pos::Int
end

mutable struct Lexer
    s::String
    i::Int
    n::Int
end

Lexer(s::String) = Lexer(s, firstindex(s), lastindex(s))

is_name_start(c::Char) = (c == '_') || isletter(c)
is_name_char(c::Char)  = (c == '_') || isletter(c) || isdigit(c)

const KEYWORDS = Set(["define","print","if","else","while","fn","return","operator","new","type"])

trace_lex_token(tok::Token) = (TRACE_LEX[] && @info "LEX" kind=tok.kind text=tok.text pos=tok.pos; tok)

function skip_ws_and_comments!(lx::Lexer)
    while lx.i <= lx.n
        c = lx.s[lx.i]
        if c in (' ', '\t', '\r', '\n')
            lx.i = nextind(lx.s, lx.i); continue
        end
        ni = (lx.i < lx.n) ? nextind(lx.s, lx.i) : lx.i
        if c == '/' && lx.i < lx.n && lx.s[ni] == '/'
            lx.i = ni
            while lx.i <= lx.n && lx.s[lx.i] != '\n'
                lx.i = nextind(lx.s, lx.i)
            end
            continue
        end
        break
    end
end

function read_string!(lx::Lexer)
    pos0 = lx.i
    lx.i = nextind(lx.s, lx.i)  # skip opening "
    buf = IOBuffer()
    while lx.i <= lx.n
        c = lx.s[lx.i]
        if c == '"'
            lx.i = nextind(lx.s, lx.i)
            return trace_lex_token(Token(:STRING, String(take!(buf)), pos0))
        elseif c == '\\'
            lx.i = nextind(lx.s, lx.i)
            lx.i > lx.n && error("unterminated escape in string at $pos0")
            esc = lx.s[lx.i]
            lx.i = nextind(lx.s, lx.i)
            if     esc == 'n';  write(buf, '\n')
            elseif esc == 't';  write(buf, '\t')
            elseif esc == 'r';  write(buf, '\r')
            elseif esc == '"';  write(buf, '"')
            elseif esc == '\\'; write(buf, '\\')
            else
                write(buf, '\\'); write(buf, esc)
            end
        else
            write(buf, c)
            lx.i = nextind(lx.s, lx.i)
        end
    end
    error("unterminated string literal starting at $pos0")
end

function next_token(lx::Lexer)
    skip_ws_and_comments!(lx)
    pos = lx.i
    if lx.i > lx.n
        return trace_lex_token(Token(:EOF, "", pos))
    end
    c = lx.s[lx.i]

    if c == '"'
        return read_string!(lx)
    end

    if is_name_start(c)
        j = nextind(lx.s, lx.i)
        while j <= lx.n && is_name_char(lx.s[j]); j = nextind(lx.s, j) end
        txt = lx.s[lx.i:prevind(lx.s, j)]
        lx.i = j
        return trace_lex_token(Token((txt in KEYWORDS) ? :KW : :NAME, txt, pos))
    end

    if isdigit(c)
        j = nextind(lx.s, lx.i); hasdot = false
        while j <= lx.n
            cj = lx.s[j]
            if cj == '.' && !hasdot
                hasdot = true; j = nextind(lx.s, j)
            elseif isdigit(cj)
                j = nextind(lx.s, j)
            else
                break
            end
        end
        txt = lx.s[lx.i:prevind(lx.s, j)]
        lx.i = j
        return trace_lex_token(Token(:NUMBER, txt, pos))
    end

    if (c == '>' || c == '<' || c == '=')
        j = (lx.i < lx.n) ? nextind(lx.s, lx.i) : lx.i
        if lx.i < lx.n && lx.s[j] == '='
            txt = string(c, '=')
            lx.i = nextind(lx.s, j)
            return trace_lex_token(Token(:OP, txt, pos))
        end
    end

    if c in ['+','-','*','/','>','<']
        lx.i = nextind(lx.s, lx.i)
        return trace_lex_token(Token(:OP, string(c), pos))
    end

    if c in ['(',')','{','}','[',']',';',',',':','=', '.']
        lx.i = nextind(lx.s, lx.i)
        return trace_lex_token(Token(:SYMBOL, string(c), pos))
    end

    error("Lexing error at position $pos (char='$(c)')")
end

########################
# AST / IR
########################

abstract type IR end

# Statements
struct Let     <: IR; name::String; expr::IR; end
struct Assign  <: IR; name::String; expr::IR; end
struct Print   <: IR; expr::IR; end
struct If      <: IR; cond::IR; then_::Vector{IR}; els::Vector{IR}; end
struct While   <: IR; cond::IR; body::Vector{IR}; end
struct Fn      <: IR; name::String; params::Vector{String}; body::Vector{IR}; end
struct CallStmt <: IR; name::String; args::Vector{IR}; end
struct Return  <: IR; expr::IR; end

struct OpDef   <: IR
    op::String
    a_name::String
    a_type::String
    b_name::String
    b_type::String
    ret_type::String
    body::Vector{IR}
end

struct DestructAssign <: IR
    names::Vector{String}
    expr::IR
end

"Named Record-Typen (erste Stufe Richtung Klassen)."
struct TypeDef <: IR
    name::String                      # z.B. "Error"
    fields::Vector{Pair{String,String}}  # z.B. "code" => "number"
end

# Expressions
struct Num    <: IR; txt::String; end
struct Str    <: IR; txt::String; end
struct Var    <: IR; name::String; end
struct Call   <: IR; name::String; args::Vector{IR}; end
struct Bin    <: IR; op::String; a::IR; b::IR; end
struct New    <: IR; size::IR; end
struct NewLit <: IR; items::Vector{IR}; end
struct ObjLit <: IR; fields::Vector{Pair{String, IR}}; end
struct Field  <: IR; obj::IR; name::String; end

########################
# Parser
########################

mutable struct Parser
    lx::Lexer
    look::Token
end

function Parser(src::String)
    lx = Lexer(src)
    Parser(lx, next_token(lx))
end

advance!(p::Parser) = (p.look = next_token(p.lx))

function expect!(p::Parser, kind::Symbol, txt::Union{Nothing,String}=nothing)
    t = p.look
    TRACE_PARSE[] && @info "EXPECT" want_kind=kind want_txt=txt got_kind=t.kind got_txt=t.text pos=t.pos
    ok = (t.kind == kind) && (txt === nothing || t.text == txt)
    if !ok
        want = string(kind); wanttxt = txt === nothing ? "" : " " * txt
        got = string(t.kind, " '", t.text, "'")
        error("Parse error near pos $(t.pos): expected $(want)$(wanttxt) but got $(got)")
    end
    advance!(p); return t
end

function accept!(p::Parser, kind::Symbol, txt::Union{Nothing,String}=nothing)
    t = p.look
    if t.kind == kind && (txt === nothing || t.text == txt)
        advance!(p); return true
    end
    false
end

function parse_program(p::Parser)
    out = IR[]
    while p.look.kind != :EOF
        push!(out, parse_stmt(p))
    end
    out
end

function parse_block(p::Parser)
    expect!(p, :SYMBOL, "{")
    out = IR[]
    while !(p.look.kind == :SYMBOL && p.look.text == "}")
        push!(out, parse_stmt(p))
    end
    expect!(p, :SYMBOL, "}")
    out
end

function parse_params(p::Parser)
    names = String[]
    if p.look.kind == :NAME
        push!(names, expect!(p, :NAME).text)
        while accept!(p, :SYMBOL, ",")
            push!(names, expect!(p, :NAME).text)
        end
    end
    names
end

function parse_args(p::Parser)
    args = IR[]
    if !(p.look.kind == :SYMBOL && p.look.text == ")")
        push!(args, parse_expr(p))
        while accept!(p, :SYMBOL, ",")
            push!(args, parse_expr(p))
        end
    end
    args
end

function default_expr_for(tname::String)::IR
    if tname == "number"; return Num("0")
    elseif tname == "string"; return Str("")
    elseif tname == "bool";   return Var("false")
    elseif tname == "any";    return Var("nothing")
    else
        # für unbekannte Typnamen einfach eine Variable mit diesem Namen
        return Var(tname)
    end
end

function parse_obj_literal(p::Parser)::IR
    expect!(p, :SYMBOL, "{")
    fields = Pair{String,IR}[]
    while !(p.look.kind == :SYMBOL && p.look.text == "}")
        fname = expect!(p, :NAME).text
        expect!(p, :SYMBOL, ":")
        if p.look.kind == :NAME && (p.look.text in ("number","string","bool","any"))
            tname = p.look.text; advance!(p)
            fexpr = default_expr_for(tname)
        else
            fexpr = parse_expr(p)
        end
        push!(fields, fname => fexpr)
        if !accept!(p, :SYMBOL, ",")
            break
        end
    end
    expect!(p, :SYMBOL, "}")
    return ObjLit(fields)
end

function parse_postfix_dot(p::Parser, base::IR)::IR
    while p.look.kind == :SYMBOL && p.look.text == "."
        advance!(p)
        fname = expect!(p, :NAME).text
        base = Field(base, fname)
    end
    return base
end

function parse_stmt(p::Parser)::IR
    t = p.look

    # Destrukturierung am Zeilenanfang: {a,b,...} = expr;
    if t.kind == :SYMBOL && t.text == "{"
        advance!(p)
        names = String[]
        push!(names, expect!(p, :NAME).text)
        while accept!(p, :SYMBOL, ",")
            push!(names, expect!(p, :NAME).text)
        end
        expect!(p, :SYMBOL, "}")
        expect!(p, :SYMBOL, "=")
        ex = parse_expr(p)
        expect!(p, :SYMBOL, ";")
        return DestructAssign(names, ex)
    end

    if t.kind == :KW
        if t.text == "define"
            advance!(p)
            name = expect!(p, :NAME).text
            expect!(p, :SYMBOL, "=")
            expr = parse_expr(p)
            expect!(p, :SYMBOL, ";")
            return Let(name, expr)

        elseif t.text == "print"
            advance!(p); expect!(p, :SYMBOL, "(")
            e = parse_expr(p)
            expect!(p, :SYMBOL, ")"); expect!(p, :SYMBOL, ";")
            return Print(e)

        elseif t.text == "if"
            advance!(p); expect!(p, :SYMBOL, "(")
            c = parse_expr(p); expect!(p, :SYMBOL, ")")
            then_blk = parse_block(p)
            els_blk = IR[]
            if p.look.kind == :KW && p.look.text == "else"
                advance!(p); els_blk = parse_block(p)
            end
            return If(c, then_blk, els_blk)

        elseif t.text == "while"
            advance!(p); expect!(p, :SYMBOL, "(")
            c = parse_expr(p); expect!(p, :SYMBOL, ")")
            body = parse_block(p)
            return While(c, body)

        elseif t.text == "fn"
            advance!(p)
            fname = expect!(p, :NAME).text
            expect!(p, :SYMBOL, "(")
            params = parse_params(p)
            expect!(p, :SYMBOL, ")")
            body = parse_block(p)
            return Fn(fname, params, body)

        elseif t.text == "return"
            advance!(p)
            e = parse_expr(p); expect!(p, :SYMBOL, ";")
            return Return(e)

        elseif t.text == "type"
            # type Name { field: Type; field2: Type2; ... }
            advance!(p)
            tname = expect!(p, :NAME).text
            expect!(p, :SYMBOL, "{")
            fields = Pair{String,String}[]
            while !(p.look.kind == :SYMBOL && p.look.text == "}")
                fname = expect!(p, :NAME).text
                expect!(p, :SYMBOL, ":")
                ftype = expect!(p, :NAME).text
                push!(fields, fname => ftype)
                # optionaler Separator , oder ;
                if accept!(p, :SYMBOL, ",") || accept!(p, :SYMBOL, ";")
                    # ok
                else
                    # kein Separator → while-Bedingung checkt auf "}"
                end
            end
            expect!(p, :SYMBOL, "}")
            return TypeDef(tname, fields)

        elseif t.text == "operator"
            advance!(p)
            op = expect!(p, :OP).text
            expect!(p, :SYMBOL, "(")
            a_name = expect!(p, :NAME).text; expect!(p, :SYMBOL, ":"); a_type = expect!(p, :NAME).text
            expect!(p, :SYMBOL, ",")
            b_name = expect!(p, :NAME).text; expect!(p, :SYMBOL, ":"); b_type = expect!(p, :NAME).text
            expect!(p, :SYMBOL, ")")
            expect!(p, :OP, "-"); expect!(p, :OP, ">")
            ret_type = expect!(p, :NAME).text
            body = parse_block(p)
            return OpDef(op, a_name, a_type, b_name, b_type, ret_type, body)
        end
    end

    if t.kind == :NAME
        name = t.text
        advance!(p)
        if accept!(p, :SYMBOL, "=")
            expr = parse_expr(p)
            expect!(p, :SYMBOL, ";")
            return Assign(name, expr)
        elseif accept!(p, :SYMBOL, "(")
            args = parse_args(p)
            expect!(p, :SYMBOL, ")"); expect!(p, :SYMBOL, ";")
            return CallStmt(name, args)
        else
            error("Parse error near pos $(t.pos): after identifier '$name' expected '=' or '('.")
        end
    end

    error("Parse error near pos $(t.pos): unexpected token $(t.kind) '$(t.text)'")
end

parse_expr(p::Parser) = parse_equality(p)

function parse_equality(p::Parser)
    left = parse_comparison(p)
    while p.look.kind == :OP && p.look.text == "=="
        advance!(p)
        right = parse_comparison(p)
        left = Bin("==", left, right)
    end
    left
end

function parse_comparison(p::Parser)
    left = parse_sum(p)
    while p.look.kind == :OP && (p.look.text in (">", ">=", "<", "<="))
        op = p.look.text; advance!(p)
        right = parse_sum(p)
        left = Bin(op, left, right)
    end
    left
end

function parse_sum(p::Parser)
    left = parse_term(p)
    while p.look.kind == :OP && (p.look.text == "+" || p.look.text == "-")
        op = p.look.text; advance!(p)
        right = parse_term(p)
        left = Bin(op, left, right)
    end
    left
end

function parse_term(p::Parser)
    left = parse_factor(p)
    while p.look.kind == :OP && (p.look.text == "*" || p.look.text == "/")
        op = p.look.text; advance!(p)
        right = parse_factor(p)
        left = Bin(op, left, right)
    end
    left
end

function parse_factor(p::Parser)
    t = p.look
    if t.kind == :KW && t.text == "new"
        advance!(p)
        if accept!(p, :SYMBOL, "(")
            e = parse_expr(p); expect!(p, :SYMBOL, ")")
            return parse_postfix_dot(p, New(e))
        elseif accept!(p, :SYMBOL, "[")
            items = IR[]
            if !(p.look.kind == :SYMBOL && p.look.text == "]")
                push!(items, parse_expr(p))
                while accept!(p, :SYMBOL, ",")
                    push!(items, parse_expr(p))
                end
            end
            expect!(p, :SYMBOL, "]")
            return parse_postfix_dot(p, NewLit(items))
        else
            error("Parse error near pos $(t.pos): expected '(' or '[' after 'new'")
        end
    elseif t.kind == :NUMBER
        advance!(p); return parse_postfix_dot(p, Num(t.text))
    elseif t.kind == :STRING
        advance!(p); return parse_postfix_dot(p, Str(t.text))
    elseif t.kind == :NAME
        name = t.text; advance!(p)
        if accept!(p, :SYMBOL, "(")
            args = parse_args(p); expect!(p, :SYMBOL, ")")
            if name == "tag" && length(args) == 2 && (args[2] isa Var)
                v = (args[2]::Var).name
                args = [args[1], Str(v)]
            end
            return parse_postfix_dot(p, Call(name, args))
        else
            return parse_postfix_dot(p, Var(name))
        end
    elseif t.kind == :SYMBOL && t.text == "{"
        base = parse_obj_literal(p)
        return parse_postfix_dot(p, base)
    elseif t.kind == :SYMBOL && t.text == "("
        advance!(p); e = parse_expr(p); expect!(p, :SYMBOL, ")")
        return parse_postfix_dot(p, e)
    else
        error("Parse error near pos $(t.pos): unexpected token in expression $(t.kind) '$(t.text)'")
    end
end

########################
# Codegen-Runtime (Julia)
########################

mutable struct Emitter
    lines::Vector{String}
    ind::Int
end
Emitter() = Emitter(String[], 0)

function emit!(em::Emitter, s::AbstractString = "")
    push!(em.lines, repeat("    ", em.ind) * String(s))
end

function mangle_op(op::String)
    if op == "+"; "add"
    elseif op == "-"; "sub"
    elseif op == "*"; "mul"
    elseif op == "/"; "div"
    elseif op == "=="; "eq"
    elseif op == ">"; "gt"
    elseif op == ">="; "ge"
    elseif op == "<"; "lt"
    elseif op == "<="; "le"
    else; error("unknown op $op")
    end
end

function jl_string_literal(s::AbstractString)
    x = replace(String(s),
                "\\" => "\\\\",
                "\"" => "\\\"",
                "\n" => "\\n",
                "\r" => "\\r",
                "\t" => "\\t")
    return "\"" * x * "\""
end

const RUNTIME_JL = """
# --- tiny runtime with overloading, records & buffered output ---
global __OUT = IOBuffer()
global __CAPTURED__ = ""

__emitln(x) = (print(__OUT, x); print(__OUT, '\\n'); nothing)

# Heap & Tags & Ops
const __heap = Dict{Int, Vector{Any}}()
const __ptr_tags = Dict{Int, String}()
const __ops = Dict{Tuple{String, Union{Nothing,String}, Union{Nothing,String}}, Function}()
__next_ptr = Ref(1)

# Fehler-Records
const __OK  = Dict("__tag__"=>"Error", "code"=>0, "msg"=>"")
__ERR(msg)  = Dict("__tag__"=>"Error", "code"=>1, "msg"=>String(msg))
__OK_REC()  = Dict("__tag__"=>"Record", "e"=>__OK)
__ERR_REC(msg) = Dict("__tag__"=>"Record", "e"=>__ERR(msg))

function __new(n)
    n < 0 && error("alloc error: negative size")
    p = __next_ptr[]
    __next_ptr[] += 1
    __heap[p] = [0 for _ in 1:Int(n)]
    return p
end

function __delete(p)
    try
        p = Int(p)
        pop!(__heap, p, nothing)
        pop!(__ptr_tags, p, nothing)
        return __OK_REC()
    catch e
        return __ERR_REC(e)
    end
end

function heap_get(p, i)
    return __heap[Int(p)][Int(i)+1]
end

function heap_set(p, i, v)
    try
        __heap[Int(p)][Int(i)+1] = v
        return __OK_REC()
    catch e
        return __ERR_REC(e)
    end
end

function tag(p, typ)
    try
        __ptr_tags[Int(p)] = String(typ)
        return __OK_REC()
    catch e
        return __ERR_REC(e)
    end
end

function __get_tag(v)
    if v isa Dict && haskey(v, "__tag__")
        return v["__tag__"]
    end
    try
        iv = Int(v)
        if haskey(__ptr_tags, iv)
            return __ptr_tags[iv]
        end
    catch
    end
    return nothing
end

function __register_op(op, ta, tb, fn)
    __ops[(String(op), ta === nothing ? nothing : String(ta), tb === nothing ? nothing : String(tb))] = fn
    return nothing
end

function __binop(op, a, b)
    ta = __get_tag(a); tb = __get_tag(b)
    key = (String(op), ta, tb)
    if haskey(__ops, key)
        return __ops[key](a, b)
    end
    op = String(op)
    if op == "+" ; return a + b
    elseif op == "-" ; return a - b
    elseif op == "*" ; return a * b
    elseif op == "/" ; return a / b
    elseif op == ">" ; return a > b
    elseif op == ">="; return a >= b
    elseif op == "<" ; return a < b
    elseif op == "<="; return a <= b
    elseif op == "=="; return a == b
    else
        error("unsupported op " * op)
    end
end

box(v) = Dict("__tag__"=>"Box", "v"=>v)
unbox(b) = b["v"]

# Struct-Felder
function field_get(o, k)
    return o[String(k)]
end
function field_set(o, k, v)
    o[String(k)] = v
    return nothing
end

# --- simple type registry for TinyLanguage ---
const __types = Dict{String,Any}()

function __register_type(name, fields::Dict{String,String})
    __types[String(name)] = Dict(
        "kind" => "record",
        "fields" => fields,
    )
    return nothing
end

function __type_field_type(tname, fname)
    T = get(__types, String(tname), nothing)
    T === nothing && return nothing
    fs = T["fields"]
    return get(fs, String(fname), nothing)
end
"""

function gen_expr(em::Emitter, e::IR)::String
    if e isa Num
        return (e::Num).txt
    elseif e isa Str
        return jl_string_literal((e::Str).txt)
    elseif e isa Var
        return (e::Var).name
    elseif e isa Call
        ee = (e::Call)
        args = [gen_expr(em, a) for a in ee.args]
        return string(ee.name, "(", join(args, ", "), ")")
    elseif e isa New
        return string("__new(", gen_expr(em, (e::New).size), ")")
    elseif e isa NewLit
        items = (e::NewLit).items
        # Heap-Initialisierung, Fehler werden ignoriert (Generator-Code, nicht Tiny)
        assignments = String[]
        for (i, it) in enumerate(items)
            push!(assignments, "heap_set(__p, $(i-1), " * gen_expr(em, it) * ")")
        end
        return "(let __p = __new(" * string(length(items)) * "); " *
               join(assignments, "; ") * "; __p end)"
    elseif e isa Bin
        ee = (e::Bin)
        return string("__binop(\"", ee.op, "\", ", gen_expr(em, ee.a), ", ", gen_expr(em, ee.b), ")")
    elseif e isa ObjLit
        pairs_src = String[]
        push!(pairs_src, "\"__tag__\"=>\"Struct\"")
        for pr in (e::ObjLit).fields
            fname, fexpr = pr.first, pr.second
            push!(pairs_src, string("\"", fname, "\"=>", gen_expr(em, fexpr)))
        end
        return string("Dict(", join(pairs_src, ", "), ")")
    elseif e isa Field
        ee = (e::Field)
        return string("field_get(", gen_expr(em, ee.obj), ", \"", ee.name, "\")")
    else
        error("unknown expr node")
    end
end

function gen_stmt!(em::Emitter, s::IR)
    if s isa Let
        emit!(em, string((s::Let).name, " = ", gen_expr(em, (s::Let).expr)))
    elseif s isa Assign
        ss = (s::Assign)
        emit!(em, string(ss.name, " = ", gen_expr(em, ss.expr)))
    elseif s isa Print
        emit!(em, "__emitln(" * gen_expr(em, (s::Print).expr) * ")")
    elseif s isa If
        ss = (s::If)
        emit!(em, string("if ", gen_expr(em, ss.cond)))
        em.ind += 1
        for st in ss.then_; gen_stmt!(em, st); end
        em.ind -= 1
        if !isempty(ss.els)
            emit!(em, "else"); em.ind += 1
            for st in ss.els; gen_stmt!(em, st); end
            em.ind -= 1
        end
        emit!(em, "end")
    elseif s isa While
        ss = (s::While)
        emit!(em, string("while ", gen_expr(em, ss.cond)))
        em.ind += 1
        for st in ss.body; gen_stmt!(em, st); end
        em.ind -= 1
        emit!(em, "end")
    elseif s isa Fn
        ss = (s::Fn)
        emit!(em, string("function ", ss.name, "(", join(ss.params, ", "), ")"))
        em.ind += 1
        if isempty(ss.body)
            emit!(em, "nothing")
        else
            for st in ss.body; gen_stmt!(em, st); end
        end
        em.ind -= 1
        emit!(em, "end")
    elseif s isa CallStmt
        ss = (s::CallStmt)
        error("call with return value must be bound; bare call statements are not allowed (offending call: $(ss.name)())")
    elseif s isa Return
        emit!(em, string("return ", gen_expr(em, (s::Return).expr)))
    elseif s isa OpDef
        ss = (s::OpDef)
        fname = string("__op_", mangle_op(ss.op), "_", ss.a_type, "_", ss.b_type)
        emit!(em, "function $(fname)($(ss.a_name), $(ss.b_name))")
        em.ind += 1
        if isempty(ss.body)
            emit!(em, "nothing")
        else
            for st in ss.body; gen_stmt!(em, st); end
        end
        em.ind -= 1
        emit!(em, "end")
        emit!(em, "__register_op(\"$(ss.op)\", \"$(ss.a_type)\", \"$(ss.b_type)\", $(fname))")
        emit!(em, "")
    elseif s isa DestructAssign
        ss = (s::DestructAssign)
        emit!(em, "__tmp_rec__ = " * gen_expr(em, ss.expr))
        for nm in ss.names
            emit!(em, string(nm, " = field_get(__tmp_rec__, \"", nm, "\")"))
        end
    elseif s isa TypeDef
        ss = (s::TypeDef)
        parts = String[]
        for pr in ss.fields
            push!(parts, "\"$(pr.first)\"=>\"$(pr.second)\"")
        end
        emit!(em, "__register_type(\"$(ss.name)\", Dict(" * join(parts, ", ") * "))")
    else
        error("unknown stmt node")
    end
end

function gen_program(stmts::Vector{IR})::String
    em = Emitter()
    emit!(em, "# generated from tiny language (Julia)")
    for ln in split(RUNTIME_JL, '\n'); emit!(em, ln); end
    emit!(em, "")

    # Operatoren zuerst
    for s in stmts
        s isa OpDef && gen_stmt!(em, s)
    end
    # Typdefinitionen
    for s in stmts
        s isa TypeDef && gen_stmt!(em, s)
    end
    # Funktionsdefinitionen
    for s in stmts
        s isa Fn && gen_stmt!(em, s)
    end

    # Main-Body
    emit!(em, "function __tiny_main__()")
    em.ind += 1
    for s in stmts
        !(s isa OpDef) && !(s isa Fn) && !(s isa TypeDef) && gen_stmt!(em, s)
    end
    em.ind -= 1
    emit!(em, "end")

    # Run-Wrapper mit Output-Capture
    emit!(em, "function __tiny_run__()")
    emit!(em, "    seek(__OUT, 0); truncate(__OUT, 0)")
    emit!(em, "    __tiny_main__()")
    emit!(em, "    global __CAPTURED__ = String(take!(__OUT))")
    emit!(em, "    return __CAPTURED__")
    emit!(em, "end")

    join(em.lines, "\n")
end

########################
# Linter (MUST-USE)
########################

function uses_in_expr(e::IR, reads::Dict{String,Int})
    if e isa Var
        nm = (e::Var).name
        reads[nm] = get(reads, nm, 0) + 1
    elseif e isa Bin
        uses_in_expr((e::Bin).a, reads)
        uses_in_expr((e::Bin).b, reads)
    elseif e isa Call
        for a in (e::Call).args
            uses_in_expr(a, reads)
        end
    elseif e isa New
        uses_in_expr((e::New).size, reads)
    elseif e isa NewLit
        for it in (e::NewLit).items
            uses_in_expr(it, reads)
        end
    elseif e isa Field
        uses_in_expr((e::Field).obj, reads)
    elseif e isa ObjLit
        for pr in (e::ObjLit).fields
            uses_in_expr(pr.second, reads)
        end
    end
end

function lint_stmt_reads!(s::IR, reads::Dict{String,Int})
    if s isa Let
        uses_in_expr((s::Let).expr, reads)
    elseif s isa Assign
        uses_in_expr((s::Assign).expr, reads)
    elseif s isa Print
        uses_in_expr((s::Print).expr, reads)
    elseif s isa If
        ss = (s::If); uses_in_expr(ss.cond, reads)
        for t in ss.then_; lint_stmt_reads!(t, reads); end
        for t in ss.els;   lint_stmt_reads!(t, reads); end
    elseif s isa While
        ss = (s::While); uses_in_expr(ss.cond, reads)
        for t in ss.body; lint_stmt_reads!(t, reads); end
    elseif s isa CallStmt
        return
    elseif s isa Return
        uses_in_expr((s::Return).expr, reads)
    elseif s isa OpDef
        # eigene Scope-Prüfung
        tmp_reads = Dict{String,Int}()
        for t in (s::OpDef).body
            lint_stmt_reads!(t, tmp_reads)
        end
        miss = String[]
        get(tmp_reads, s.a_name, 0) == 0 && push!(miss, s.a_name)
        get(tmp_reads, s.b_name, 0) == 0 && push!(miss, s.b_name)
        if !isempty(miss)
            error("unused operator parameter(s) in op $(s.op): " * join(miss, ", "))
        end
    elseif s isa DestructAssign
        uses_in_expr((s::DestructAssign).expr, reads)
    elseif s isa TypeDef
        # keine Variablenzugriffe
        return
    end
end

function lint_fn_params_used!(f::Fn)
    reads = Dict{String,Int}()
    for st in f.body
        lint_stmt_reads!(st, reads)
    end
    unused = [p for p in f.params if get(reads, p, 0) == 0]
    if !isempty(unused)
        error("unused parameter(s) in function $(f.name): " * join(unused, ", "))
    end
    lint_locals_used!(f.body)
end

function lint_locals_used!(stmts::Vector{IR})
    defs = Dict{String,Int}()
    uses = Dict{String,Int}()
    for (i, s) in enumerate(stmts)
        if s isa Let
            defs[(s::Let).name] = i
        elseif s isa DestructAssign
            for nm in (s::DestructAssign).names
                defs[nm] = i
            end
        end
    end
    for s in stmts
        lint_stmt_reads!(s, uses)
    end
    unused = [n for (n, _) in defs if get(uses, n, 0) == 0]
    if !isempty(unused)
        error("unused local binding(s): " * join(unused, ", "))
    end
end

########################
# Driver
########################

function compile_to_julia(src::String)::String
    p = Parser(src)
    ir = parse_program(p)

    # Lint
    for s in ir
        s isa Fn && lint_fn_params_used!(s)
    end
    lint_locals_used!(ir)

    gen_program(ir)
end

# CLI-Modus, wenn Datei direkt aufgerufen wird
if abspath(PROGRAM_FILE) == @__FILE__
    if length(ARGS) < 1
        println("Usage: julia tiny_lang.jl <source.tiny> [--emit out.jl] [--run] [--trace-lex] [--trace-parse]")
        exit(0)
    end
    if any(==("--trace-lex"), ARGS);   TRACE_LEX[] = true;   end
    if any(==("--trace-parse"), ARGS); TRACE_PARSE[] = true; end

    # robuste Pfadauflösung
    src_arg = ARGS[1]
    function resolve_src(arg::AbstractString)
        if isabspath(arg) && isfile(arg); return arg; end
        p1 = joinpath(@__DIR__, arg);                 isfile(p1) && return p1
        p2 = joinpath(@__DIR__, "TinyLanguage", arg); isfile(p2) && return p2
        p3 = joinpath(pwd(), arg);                    isfile(p3) && return p3
        error("Source file not found: $arg\n  @__DIR__=$(abspath(@__DIR__))\n  pwd()=$(abspath(pwd()))")
    end
    src_path = resolve_src(src_arg)
    src = read(src_path, String)

    code = try
        compile_to_julia(src)
    catch err
        showerror(stdout, err, catch_backtrace()); println()
        exit(1)
    end

    if any(==("--emit"), ARGS)
        idx = findfirst(==("--emit"), ARGS)
        outpath = (idx !== nothing && idx < length(ARGS)) ? ARGS[idx+1] : "out.jl"
        open(outpath, "w") do io; write(io, code); end
        println("Wrote ", outpath)
    end

    if any(==("--run"), ARGS)
        mod = Module()
        Base.include_string(mod, code)
        f = getfield(mod, :__tiny_run__)
        Base.invokelatest(f)
        println(mod.__CAPTURED__)
    elseif !any(==("--emit"), ARGS)
        println("Compilation successful. Use --emit out.jl or --run.")
    end
end

end # module TinyLanguage
