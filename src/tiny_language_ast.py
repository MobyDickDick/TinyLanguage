# ----- AST Nodes -----


class IR:
    pass


@dataclass
class Let(IR):
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Assign(IR):
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class FieldAssign(IR):
    obj: IR
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Print(IR):
    exprs: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class If(IR):
    cond: IR
    then: List[IR]
    els: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class While(IR):
    cond: IR
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class TryCatch(IR):
    body: List[IR]
    err_name: Optional[str]
    handler: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Param:
    name: str
    type: Optional[str] = None


@dataclass
class Fn(IR):
    name: str
    params: List[Param]
    body: List[IR]
    namespace: Optional[str] = None
    return_type: Optional[str] = None
    is_async: bool = False
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodDef(IR):
    class_name: str
    name: str
    params: List[Param]
    body: List[IR]
    return_type: Optional[str] = None
    namespace: Optional[str] = None
    is_async: bool = False
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Namespace(IR):
    name: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Return(IR):
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Import(IR):
    module: str
    alias: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class CallStmt(IR):
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class OpDef(IR):
    op: str
    a_name: str
    a_type: str
    b_name: str
    b_type: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class DestructAssign(IR):
    names: List[str]
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class TypeVariant:
    name: str
    fields: List[Tuple[str, str]]


@dataclass
class TypeDef(IR):
    name: str
    fields: Optional[List[Tuple[str, str]]] = None
    variants: Optional[List[TypeVariant]] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassDef(IR):
    name: str
    fields: List[Tuple[str, str]]
    methods: List["MethodDef"]
    bases: List[str]
    pos: SourcePos = field(default_factory=SourcePos.origin)


# Expressions
@dataclass
class Num(IR):
    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Str(IR):
    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bool(IR):
    value: bool
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Null(IR):
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Var(IR):
    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Call(IR):
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class New(IR):
    size: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class NewLit(IR):
    items: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bin(IR):
    op: str
    a: IR
    b: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ObjLit(IR):
    fields: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Field(IR):
    obj: IR
    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodCall(IR):
    obj: IR
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassNew(IR):
    name: str
    init: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Spawn(IR):
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Await(IR):
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MatchCase:
    pattern: "Pattern"
    body: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


class Pattern:
    pos: SourcePos


@dataclass
class VariantPattern(Pattern):
    variant: str
    bindings: Dict[str, Optional[str]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class WildcardPattern(Pattern):
    name: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Match(IR):
    expr: IR
    cases: List[MatchCase]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class VariantCtor(IR):
    variant: str
    fields: List[Tuple[str, IR]]
    type_name: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


