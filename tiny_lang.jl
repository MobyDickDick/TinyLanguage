module TinyLanguage

"""
Mini-Compiler für eine winzige, C-ähnliche Sprache. Die Übersetzung läuft in
vier Schritten:

1. **Lexer**: zerlegt den Quelltext in Tokens.
2. **Parser**: baut aus den Tokens eine kleine IR (Abstract Syntax Tree).
3. **Linter**: erzwingt MUST-USE-Regeln (Parameter + lokale Bindungen nutzen).
4. **Codegen**: erzeugt Julia-Quelltext samt tiny Runtime und führt ihn auf
   Wunsch direkt aus.

Alle Bausteine sind in dieser einen Datei enthalten, sodass man bequem
nachvollziehen kann, wie Lexer/Parser/Emitter ineinandergreifen.
"""

# tiny_lang.jl — Mini-Sprache (Lexer → Parser/IR → Linter → Julia-Codegen)
# Features:
#   - define, Zuweisung, print, if/else, while, fn, return, operator-Overloads
#   - Arrays: new(n) und new[items...] (0-basierte Indizes für heap_*)
#   - Strings mit Escapes \" \\ \n \r \t
#   - Struct-Literale: { field: expr, ... } (+ Kurzschema number/string/bool/any)
#   - Feldzugriff: obj.field
#   - Destrukturierung zu Record: {a, b} = expr;
#   - type-Definitionen: type Name { field: Type; ... }
#   - Klassen: class Name { field: Type; fn method(self, ...) { ... } }
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

const KEYWORDS = Set(["define","print","if","else","while","fn","return","operator","new","type","class"])

trace_lex_token(tok::Token) = (TRACE_LEX[] && @info "LEX" kind=tok.kind text=tok.text pos=tok.pos; tok)

"""
    skip_ws_and_comments!(lx)

Überspringt Whitespace und `//`-Zeilenkommentare. Aktualisiert den
Lexer-Index, ohne Tokens zu erzeugen, damit `next_token` direkt am nächsten
relevanten Zeichen fortsetzen kann.
"""
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

"""
    read_string!(lx)

Liest ein Stringliteral inklusive Escape-Handling (`\n`, `\t`, `\\`, `\"`).
Gibt ein fertiges `Token(:STRING, ...)` zurück und hebt einen Fehler aus, wenn
das schließende Anführungszeichen fehlt.
"""
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

"""
    next_token(lx)

Liefert das nächste Token und rückt den Lexer-Index entsprechend vor. Hier
werden Keywords, Nummern, Operatoren und Sonderzeichen erkannt.
"""
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
struct FieldAssign <: IR; obj::IR; name::String; expr::IR; end

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

"Klassen-Definition mit Feldern und Methoden."
struct ClassDef <: IR
    name::String
    fields::Vector{Pair{String,String}}
    methods::Vector{IR}
end

"Methodendefinition innerhalb einer Klasse."
struct MethodDef <: IR
    class_name::String
    name::String
    params::Vector{String}
    body::Vector{IR}
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
struct MethodCall <: IR; obj::IR; name::String; args::Vector{IR}; end
struct ClassNew   <: IR; name::String; init::Vector{Pair{String, IR}}; end

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

"""
    parse_program(p)

Parst den vollständigen Quelltext bis `:EOF` und liefert einen Vektor aus
IR-Knoten (Statements). Fehler werden mit genauer Positionsangabe geworfen.
"""
function parse_program(p::Parser)
    out = IR[]
    while p.look.kind != :EOF
        push!(out, parse_stmt(p))
    end
    out
end

"""
    parse_block(p)

Parst einen Block `{ ... }` und gibt die enthaltenen Statements als Vektor
zurück. Die schließende Klammer wird konsumiert.
"""
function parse_block(p::Parser)
    expect!(p, :SYMBOL, "{")
    out = IR[]
    while !(p.look.kind == :SYMBOL && p.look.text == "}")
        push!(out, parse_stmt(p))
    end
    expect!(p, :SYMBOL, "}")
    out
end

"""
    parse_params(p)

Liest Funktions-Parameterliste `a, b, c` (ohne Klammern) und gibt sie als
`Vector{String}` zurück.
"""
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

"""
    parse_args(p)

Parst eine Argumentliste innerhalb von `(...)` für Aufrufe. Liefert einen
Vektor aus Expressions.
"""
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

"""
    parse_obj_literal(p)

Parst ein Objektliteral `{ field: expr, ... }`. Kurzformen wie `field: number`
werden mit Default-Werten gefüllt, damit der Generator später sinnvolle Werte
setzen kann.
"""
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

"""
    parse_postfix_dot(p, base)

Kettet beliebig viele `.feld`-Zugriffe oder Methoden-Aufrufe an einen
Basis-Ausdruck. Dadurch können `foo.bar.baz()` ohne separate Parser-Regeln
abgehandelt werden.
"""
function parse_postfix_dot(p::Parser, base::IR)::IR
    while p.look.kind == :SYMBOL && p.look.text == "."
        advance!(p)
        fname = expect!(p, :NAME).text
        if accept!(p, :SYMBOL, "(")
            args = parse_args(p)
            expect!(p, :SYMBOL, ")")
            base = MethodCall(base, fname, args)
        else
            base = Field(base, fname)
        end
    end
    return base
end

"""
    parse_stmt(p)

Parst ein einzelnes Statement (inklusive Destrukturierung, if/while, fn,
type-Definition, Operator-Definition und Ausdrücke mit Semikolon). Gibt einen
passenden IR-Knoten zurück.
"""
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

        elseif t.text == "class"
            advance!(p)
            cname = expect!(p, :NAME).text
            expect!(p, :SYMBOL, "{")
            fields = Pair{String,String}[]
            methods = IR[]
            while !(p.look.kind == :SYMBOL && p.look.text == "}")
                if p.look.kind == :KW && p.look.text == "fn"
                    advance!(p)
                    mname = expect!(p, :NAME).text
                    expect!(p, :SYMBOL, "(")
                    params = parse_params(p)
                    isempty(params) && error("method $(cname).$(mname) needs a receiver parameter (e.g. self)")
                    expect!(p, :SYMBOL, ")")
                    body = parse_block(p)
                    push!(methods, MethodDef(cname, mname, params, body))
                else
                    fname = expect!(p, :NAME).text
                    expect!(p, :SYMBOL, ":")
                    ftype = expect!(p, :NAME).text
                    push!(fields, fname => ftype)
                    accept!(p, :SYMBOL, ";")
                    accept!(p, :SYMBOL, ",")
                end
            end
            expect!(p, :SYMBOL, "}")
            return ClassDef(cname, fields, methods)
        end
    end

    if t.kind == :NAME
        name = t.text
        advance!(p)
        if accept!(p, :SYMBOL, "(")
            args = parse_args(p)
            expect!(p, :SYMBOL, ")"); expect!(p, :SYMBOL, ";")
            return CallStmt(name, args)
        end
        lhs = parse_postfix_dot(p, Var(name))
        if accept!(p, :SYMBOL, "=")
            expr = parse_expr(p)
            expect!(p, :SYMBOL, ";")
            if lhs isa Field
                lf = (lhs::Field)
                return FieldAssign(lf.obj, lf.name, expr)
            elseif lhs isa Var
                return Assign((lhs::Var).name, expr)
            else
                error("invalid assignment target")
            end
        else
            error("Parse error near pos $(t.pos): after identifier '$name' expected '=', '(', or field access.")
        end
    end

    error("Parse error near pos $(t.pos): unexpected token $(t.kind) '$(t.text)'")
end

"""
    parse_expr(p)

Einstiegspunkt für Expressions. Nutzt rekursiv die Präzedenzkaskade
`parse_equality → parse_comparison → parse_sum → parse_term → parse_factor`.
"""
parse_expr(p::Parser) = parse_equality(p)

"""
    parse_equality(p)

Parst `==`-Verkettungen linksassoziativ (z. B. `a == b == c`).
"""
function parse_equality(p::Parser)
    left = parse_comparison(p)
    while p.look.kind == :OP && p.look.text == "=="
        advance!(p)
        right = parse_comparison(p)
        left = Bin("==", left, right)
    end
    left
end

"""
    parse_comparison(p)

Parst Vergleichsoperatoren `> >= < <=` linksassoziativ.
"""
function parse_comparison(p::Parser)
    left = parse_sum(p)
    while p.look.kind == :OP && (p.look.text in (">", ">=", "<", "<="))
        op = p.look.text; advance!(p)
        right = parse_sum(p)
        left = Bin(op, left, right)
    end
    left
end

"""
    parse_sum(p)

Parst `+` und `-` linksassoziativ.
"""
function parse_sum(p::Parser)
    left = parse_term(p)
    while p.look.kind == :OP && (p.look.text == "+" || p.look.text == "-")
        op = p.look.text; advance!(p)
        right = parse_term(p)
        left = Bin(op, left, right)
    end
    left
end

"""
    parse_term(p)

Parst `*` und `/` linksassoziativ.
"""
function parse_term(p::Parser)
    left = parse_factor(p)
    while p.look.kind == :OP && (p.look.text == "*" || p.look.text == "/")
        op = p.look.text; advance!(p)
        right = parse_factor(p)
        left = Bin(op, left, right)
    end
    left
end

"""
    parse_factor(p)

Behandelt Primärausdrücke (Literale, Variablen, Aufrufe, `new`, Objekt- und
Klammerausdrücke) und hängt eventuelle `.feld`-Zugriffe an.
"""
function parse_factor(p::Parser)
    t = p.look
    if t.kind == :KW && t.text == "new"
        advance!(p)
        if p.look.kind == :NAME
            cname = expect!(p, :NAME).text
            if accept!(p, :SYMBOL, "{")
                inits = Pair{String,IR}[]
                while !(p.look.kind == :SYMBOL && p.look.text == "}")
                    fname = expect!(p, :NAME).text
                    expect!(p, :SYMBOL, ":")
                    push!(inits, fname => parse_expr(p))
                    accept!(p, :SYMBOL, ";")
                    accept!(p, :SYMBOL, ",")
                end
                expect!(p, :SYMBOL, "}")
                return parse_postfix_dot(p, ClassNew(cname, inits))
            else
                return parse_postfix_dot(p, ClassNew(cname, Pair{String,IR}[]))
            end
        elseif accept!(p, :SYMBOL, "(")
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
            error("Parse error near pos $(t.pos): expected '(', '[' or class name after 'new'")
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

"""
    Emitter

Sammelt erzeugte Julia-Codezeilen und kümmert sich um Einrückung. Der
Emitter selbst ist sehr simpel: `emit!` hängt Strings mit dem aktuellen
Indent (`ind`) an den Puffer `lines` an.
"""
mutable struct Emitter
    lines::Vector{String}
    ind::Int
end
Emitter() = Emitter(String[], 0)

"""
    emit!(em, s="")

Fügt eine neue Codezeile mit aktueller Einrückung hinzu. Leere Strings werden
als blank lines geschrieben.
"""
function emit!(em::Emitter, s::AbstractString = "")
    push!(em.lines, repeat("    ", em.ind) * String(s))
end

"""
    mangle_op(op)

Erzeugt einen eindeutigen Funktionssuffix für Operator-Overloads (z. B. `+`
→ `add`).
"""
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

"""
    jl_string_literal(s)

Escaped einen beliebigen String, damit er sicher als Julia-Stringliteral im
generierten Code verwendet werden kann.
"""
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
const __heap = Dict{Int, Vector{Any}}()  # Pointer → Value-Vektor
const __ptr_tags = Dict{Int, String}()    # Pointer → Typname
const __ops = Dict{Tuple{String, Union{Nothing,String}, Union{Nothing,String}}, Function}()  # (op, ta, tb) → Fn
const __methods = Dict{Tuple{String,String}, Function}()  # (class, name) → Fn
__next_ptr = Ref(1)  # nächste freie Pointer-ID

# Fehler-Records
const __OK  = Dict("__tag__"=>"Error", "code"=>0, "msg"=>"")
__ERR(msg)  = Dict("__tag__"=>"Error", "code"=>1, "msg"=>String(msg))
__OK_REC()  = Dict("__tag__"=>"Record", "e"=>__OK)
__ERR_REC(msg) = Dict("__tag__"=>"Record", "e"=>__ERR(msg))

function __new(n)
    n < 0 && error("alloc error: negative size")  # nur positive Längen erlaubt
    p = __next_ptr[]  # aktuelle Pointer-ID merken
    __next_ptr[] += 1  # für nächste Allocation erhöhen
    __heap[p] = [0 for _ in 1:Int(n)]  # einfachen Null-Vektor anlegen
    return p  # Pointer zurückgeben
end

function __delete(p)
    try
        p = Int(p)  # pointer in Integer casten
        pop!(__heap, p, nothing)      # Speicher freigeben (silent, falls fehlend)
        pop!(__ptr_tags, p, nothing)  # evtl. Tag-Eintrag entfernen
        return __OK_REC()             # Erfolg als Record zurückgeben
    catch e
        return __ERR_REC(e)
    end
end

# Öffentliche Wrapper-Funktion, damit Tiny-Code delete(...) aufrufen kann
# (wurde nach Projekt-Umzug verloren, weil nur __delete existierte).
# explizit als function ... end, um sicher eine globale Bindung anzulegen
# (manche Julia-Versionen warnen sonst vor fehlender Definition).
function delete(p)
    return __delete(p)
end

function heap_get(p, i)
    return __heap[Int(p)][Int(i)+1]  # +1, weil Julia 1-basiert indiziert
end

function heap_set(p, i, v)
    try
        __heap[Int(p)][Int(i)+1] = v  # Schreibzugriff auf Heap-Slot
        return __OK_REC()             # Erfolg
    catch e
        return __ERR_REC(e)
    end
end

function tag(p, typ)
    try
        __ptr_tags[Int(p)] = String(typ)  # Typnamen am Pointer speichern
        return __OK_REC()                 # Erfolgscode zurückgeben
    catch e
        return __ERR_REC(e)
    end
end

function __get_tag(v)
    if v isa Dict && haskey(v, "__tag__")
        return v["__tag__"]             # Records/Boxen tragen __tag__ direkt
    end
    try
        iv = Int(v)                      # Pointer zu Int casten (kann fehlschlagen)
        if haskey(__ptr_tags, iv)
            return __ptr_tags[iv]        # Heap-Tag finden
        end
    catch
    end
    return nothing                       # kein Tag bekannt
end

function __register_op(op, ta, tb, fn)
    __ops[(String(op), ta === nothing ? nothing : String(ta), tb === nothing ? nothing : String(tb))] = fn  # Overload
    return nothing  # nur Seiteneffekt
end

function __binop(op, a, b)
    ta = __get_tag(a); tb = __get_tag(b)  # Typ-Informationen der Operanden holen
    key = (String(op), ta, tb)
    if haskey(__ops, key)
        return __ops[key](a, b)           # benutzerdefinierten Operator ausführen
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

box(v) = Dict("__tag__"=>"Box", "v"=>v)  # Wert in einfaches Record-Boxing legen
unbox(b) = b["v"]                          # Wert aus Box holen

# Struct-Felder
function field_get(o, k)
    return o[String(k)]  # generischer Feldzugriff (Dict-basiert)
end
function field_set(o, k, v)
    o[String(k)] = v     # mutiert das Record-Dict
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

function __register_class(name, fields::Dict{String,String})
    __types[String(name)] = Dict(
        "kind" => "class",
        "fields" => fields,
    )
    return nothing
end

function __register_method(class_name, method_name, fn)
    __methods[(String(class_name), String(method_name))] = fn
    return nothing
end

function __instantiate_class(name, init_fields::Dict{String,Any})
    n = String(name)
    info = get(__types, n, nothing)
    info === nothing && error("unknown class " * n)
    obj = Dict("__tag__"=>n)
    for (fname, _) in info["fields"]
        obj[String(fname)] = nothing
    end
    for (k,v) in init_fields
        obj[String(k)] = v
    end
    return obj
end

function __call_method(obj, method, args...)
    cname = __get_tag(obj)
    cname === nothing && error("method call on untagged value")
    key = (String(cname), String(method))
    if haskey(__methods, key)
        return __methods[key](obj, args...)
    end
    error("no method " * String(method) * " for class " * String(cname))
end

function __type_field_type(tname, fname)
    T = get(__types, String(tname), nothing)
    T === nothing && return nothing
    fs = T["fields"]
    return get(fs, String(fname), nothing)
end
"""

"""
    gen_expr(em, e)

Übersetzt einen Ausdrucksknoten in Julia-Quelltext. Die Funktion ist rein
rekursiv und erzeugt Strings, die später in den Code-Emitter eingefügt werden.
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
    elseif e isa MethodCall
        ee = (e::MethodCall)
        args = [gen_expr(em, a) for a in ee.args]
        return string("__call_method(", gen_expr(em, ee.obj), ", \"", ee.name, "\"",
                      isempty(args) ? ")" : ", " * join(args, ", ") * ")")
    elseif e isa ClassNew
        ee = (e::ClassNew)
        init_pairs = [string("\"", pr.first, "\"=>", gen_expr(em, pr.second)) for pr in ee.init]
        init_src = "Dict(" * join(init_pairs, ", ") * ")"
        return string("__instantiate_class(\"", ee.name, "\", ", init_src, ")")
    else
        error("unknown expr node")
    end
end

"""
    gen_stmt!(em, s)

Erzeugt Julia-Code für ein einzelnes Statement und hängt ihn an den Emitter.
Einrückungen werden automatisch angepasst.
"""
function gen_stmt!(em::Emitter, s::IR)
    if s isa Let
        emit!(em, string((s::Let).name, " = ", gen_expr(em, (s::Let).expr)))
    elseif s isa Assign
        ss = (s::Assign)
        emit!(em, string(ss.name, " = ", gen_expr(em, ss.expr)))
    elseif s isa FieldAssign
        ss = (s::FieldAssign)
        emit!(em, string("field_set(", gen_expr(em, ss.obj), ", \"", ss.name, "\", ", gen_expr(em, ss.expr), ")"))
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
    elseif s isa ClassDef
        ss = (s::ClassDef)
        parts = String[]
        for pr in ss.fields
            push!(parts, "\"$(pr.first)\"=>\"$(pr.second)\"")
        end
        emit!(em, "__register_class(\"$(ss.name)\", Dict(" * join(parts, ", ") * "))")
        emit!(em, "")
        for m in ss.methods
            mm = (m::MethodDef)
            fname = "__method_$(ss.name)_$(mm.name)"
            emit!(em, "function $(fname)($(join(mm.params, ", ")))")
            em.ind += 1
            if isempty(mm.body)
                emit!(em, "nothing")
            else
                for st in mm.body; gen_stmt!(em, st); end
            end
            em.ind -= 1
            emit!(em, "end")
            emit!(em, "__register_method(\"$(ss.name)\", \"$(mm.name)\", $(fname))")
            emit!(em, "")
        end
    else
        error("unknown stmt node")
    end
end

"""
    gen_program(stmts)

Erzeugt den kompletten Julia-Quelltext: zuerst die tiny Runtime, dann
Operator-Definitionen, Typen, Funktionen und schließlich den Programmkörper
plus `__tiny_run__`-Wrapper zum Output-Capturing.
"""
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
    # Klassen
    for s in stmts
        s isa ClassDef && gen_stmt!(em, s)
    end
    # Funktionsdefinitionen
    for s in stmts
        s isa Fn && gen_stmt!(em, s)
    end

    # Main-Body
    emit!(em, "function __tiny_main__()")
    em.ind += 1
    for s in stmts
        !(s isa OpDef) && !(s isa Fn) && !(s isa TypeDef) && !(s isa ClassDef) && gen_stmt!(em, s)
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

"""
    uses_in_expr(e, reads)

Traversiert einen Ausdruck und zählt Variablennutzungen in `reads`. Wird vom
Linter genutzt, um MUST-USE-Verstöße aufzuspüren.
"""
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
    elseif e isa MethodCall
        ee = (e::MethodCall)
        uses_in_expr(ee.obj, reads)
        for a in ee.args; uses_in_expr(a, reads); end
    elseif e isa ClassNew
        for pr in (e::ClassNew).init
            uses_in_expr(pr.second, reads)
        end
    elseif e isa ObjLit
        for pr in (e::ObjLit).fields
            uses_in_expr(pr.second, reads)
        end
    end
end

"""
    lint_stmt_reads!(stmt, reads)

Traversiert ein Statement rekursiv und zählt alle Variablennutzungen. Für
Operator-Definitionen wird eine eigene Zählung mit Pflichtparametern
durchgeführt.
"""
function lint_stmt_reads!(s::IR, reads::Dict{String,Int})
    if s isa Let
        uses_in_expr((s::Let).expr, reads)
    elseif s isa Assign
        uses_in_expr((s::Assign).expr, reads)
    elseif s isa FieldAssign
        ss = (s::FieldAssign)
        uses_in_expr(ss.obj, reads)
        uses_in_expr(ss.expr, reads)
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
    elseif s isa MethodDef
        tmp_reads = Dict{String,Int}()
        for t in s.body
            lint_stmt_reads!(t, tmp_reads)
        end
        miss = String[]
        for p in s.params
            get(tmp_reads, p, 0) == 0 && push!(miss, p)
        end
        if !isempty(miss)
            error("unused parameter(s) in method $(s.class_name).$(s.name): " * join(miss, ", "))
        end
    end
end

"""
    lint_fn_params_used!(fn)

Verifiziert, dass alle Funktionsparameter mindestens einmal verwendet werden
und delegiert anschließend an `lint_locals_used!` für lokale Bindungen.
"""
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

function lint_fn_params_used!(m::MethodDef)
    reads = Dict{String,Int}()
    for st in m.body
        lint_stmt_reads!(st, reads)
    end
    unused = [p for p in m.params if get(reads, p, 0) == 0]
    if !isempty(unused)
        error("unused parameter(s) in method $(m.class_name).$(m.name): " * join(unused, ", "))
    end
    lint_locals_used!(m.body)
end

"""
    lint_locals_used!(stmts)

Sucht alle Top-Level-Bindungen und prüft, ob sie in den Statements gelesen
werden. Hebt einen Fehler aus, sobald ungenutzte Variablen gefunden werden.
"""
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

"""
    compile_to_julia(src) -> String

Haupteinstieg: parst den TinyLanguage-Quelltext, lintet ihn und gibt den
generierten Julia-Code (inkl. Runtime) als String zurück.
"""
function compile_to_julia(src::String)::String
    p = Parser(src)
    ir = parse_program(p)

    # Lint
    for s in ir
        s isa Fn && lint_fn_params_used!(s)
        if s isa ClassDef
            for m in (s::ClassDef).methods
                lint_fn_params_used!(m::MethodDef)
            end
        end
    end
    lint_locals_used!(ir)

    gen_program(ir)
end

"""
    write_emitted_code(outpath, code)

Schreibt den generierten Julia-Code in eine Datei über einen expliziten
`open`/`write`-Pfad, sodass keine betriebssystemspezifische `sendfile`-
Optimierung beteiligt ist. Das umgeht die VSCode-Diagnose zu potenziell
falschen Aufrufargumenten von `sendfile`, die unter Windows auftreten kann.
"""
function write_emitted_code(outpath::AbstractString, code::AbstractString)
    mkpath(dirname(outpath))
    open(outpath, "w") do io
        write(io, code)
    end
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
    """
        resolve_src(arg)

    Sucht die angegebene Quelldatei relativ zu `@__DIR__`, zu einem möglichen
    Unterordner `TinyLanguage` oder zum aktuellen Arbeitsverzeichnis. Wirkt
    damit robust gegenüber Projekt-Umzügen.
    """
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

        write_emitted_code(outpath, code)
        println("Wrote ", outpath)
    end

    if any(==("--run"), ARGS)
        mod = Module()
        Base.include_string(mod, code)
        # __tiny_run__ wird erst beim dynamischen Laden des Strings erzeugt.
        # Da Base.include_string neuen Code in einer frischen Welt einführt,
        # greifen wir über invokelatest sowohl auf das Binding als auch auf den
        # Call zu, damit keine World-Age-Warnungen (Julia ≥1.12) ausgelöst werden.
        f = Base.invokelatest(() -> getfield(mod, :__tiny_run__))
        Base.invokelatest(f)
        println(mod.__CAPTURED__)
    elseif !any(==("--emit"), ARGS)
        println("Compilation successful. Use --emit out.jl or --run.")
    end
end

end # module TinyLanguage
