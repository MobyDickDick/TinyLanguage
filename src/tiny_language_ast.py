"""Abstract syntax tree nodes for the TinyLanguage front-end.

The dataclasses here intentionally stay lightweight so the lexer, parser, and
transpilers can share a common shape without depending on runtime state. Each
node carries a ``SourcePos`` to keep error reporting consistent across
compilation stages.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from tiny_errors import SourcePos

# ----- AST Nodes -----


class IR:
    """Base class for all TinyLanguage AST nodes."""


@dataclass
class Let(IR):
    """Declaration that binds an immutable name to an expression."""

    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Assign(IR):
    """Reassignment of an existing variable."""

    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class FieldAssign(IR):
    """Assign into a field on an object literal or class instance."""

    obj: IR
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Print(IR):
    """Print one or more expressions in order."""

    exprs: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Flush(IR):
    """Flush buffered output streams."""

    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class If(IR):
    """Conditional branch with optional else body."""

    cond: IR
    then: List[IR]
    els: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class While(IR):
    """Loop that repeats while the condition evaluates truthy."""

    cond: IR
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class TryCatch(IR):
    """Exception handling block with optional error binding."""

    body: List[IR]
    err_name: Optional[str]
    handler: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Param:
    """Function or method parameter with an optional type hint."""

    name: str
    type: Optional[str] = None


@dataclass
class Fn(IR):
    """Function declaration with parameters and optional return type."""

    name: str
    params: List[Param]
    body: List[IR]
    return_param_names: Set[str] = field(default_factory=set)
    namespace: Optional[str] = None
    return_type: Optional[str] = None
    inferred_return_type: Optional[str] = None
    is_async: bool = False
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodDef(IR):
    """Method definition inside a class, mirroring ``Fn`` with a receiver."""

    class_name: str
    name: str
    params: List[Param]
    body: List[IR]
    return_param_names: Set[str] = field(default_factory=set)
    return_type: Optional[str] = None
    inferred_return_type: Optional[str] = None
    namespace: Optional[str] = None
    is_async: bool = False
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Namespace(IR):
    """Group of statements that share a namespace qualifier."""

    name: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Return(IR):
    """Return a value from the current function or method."""

    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Import(IR):
    """Import another module, optionally with an alias."""

    module: str
    alias: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class CallStmt(IR):
    """Standalone call where the result is intentionally discarded."""

    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class OpDef(IR):
    """Operator overload expressed as a function body."""

    op: str
    a_name: str
    a_type: str
    b_name: str
    b_type: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class DestructAssign(IR):
    """Destructure a record-like value into multiple bindings."""

    names: List[str]
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class TypeVariant:
    """Single variant inside an algebraic data type definition."""

    name: str
    fields: List[Tuple[str, str]]


@dataclass
class TypeDef(IR):
    """Record type or algebraic data type definition."""

    name: str
    fields: Optional[List[Tuple[str, str]]] = None
    variants: Optional[List[TypeVariant]] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassDef(IR):
    """Class declaration including fields, methods, and bases."""

    name: str
    fields: List[Tuple[str, str]]
    methods: List["MethodDef"]
    bases: List[str]
    pos: SourcePos = field(default_factory=SourcePos.origin)


# Expressions
@dataclass
class Num(IR):
    """Numeric literal preserved as text for formatting purposes."""

    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Str(IR):
    """String literal node."""

    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bool(IR):
    """Boolean literal node."""

    value: bool
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Null(IR):
    """Null literal node."""

    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Var(IR):
    """Identifier reference."""

    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Call(IR):
    """Function call expression."""

    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class New(IR):
    """Heap allocation of a fixed-size buffer."""

    size: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class NewLit(IR):
    """Heap allocation expression (vector or tuple literal)."""

    items: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bin(IR):
    """Binary operator application."""

    op: str
    a: IR
    b: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ObjLit(IR):
    """Inline object literal with named fields."""

    fields: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Field(IR):
    """Field access on a struct or object."""

    obj: IR
    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodCall(IR):
    """Method invocation on an object."""

    obj: IR
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassNew(IR):
    """Instantiate a class with an initializer field list."""

    name: str
    init: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Spawn(IR):
    """Spawn a concurrent task that evaluates a function call."""

    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Await(IR):
    """Await the result of a previously spawned task."""

    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MatchCase:
    """Single case within a ``match`` expression."""

    pattern: "Pattern"
    body: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


class Pattern:
    """Base class for match patterns."""

    pos: SourcePos


@dataclass
class VariantPattern(Pattern):
    """Match against a tagged union variant and bind fields."""

    variant: str
    bindings: Dict[str, Optional[str]]
    positional_bindings: Optional[List[Optional[str]]] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class WildcardPattern(Pattern):
    """Catch-all pattern that can optionally bind the matched value."""

    name: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Match(IR):
    """Match expression that dispatches over variants."""

    expr: IR
    cases: List[MatchCase]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class VariantCtor(IR):
    """Constructor call for a specific variant of an algebraic data type."""

    variant: str
    fields: List[Tuple[str, IR]]
    type_name: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)

