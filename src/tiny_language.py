"""Compatible public facade for TinyLanguage's ordinary implementation modules.

Implementation dependencies are explicit: AST/lexer -> parser/analysis/backends,
AST/environment/resolver -> evaluator -> runtime -> API. This module only
re-exports names; it never reads, compiles or executes implementation source.
The repository-root shim and installed CLI both use this same implementation.

Named imports preserve the historical facade, including private helpers used by
existing integrations. Implementation modules import their own dependencies;
adding an export here must never be required to make another module work.
"""

import argparse
import ast
import ctypes
import importlib
import json
import logging
import math
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import threading
import time

from collections import (
    deque,
)
from dataclasses import (
    dataclass,
    field,
)
from functools import (
    lru_cache,
)
from native_ir import (
    ClassIR,
    FunctionIR,
    Instruction,
    Opcode,
    OperatorOverloadIR,
    ProgramIR,
    TypeIR,
)
from native_python_bytecode import (
    run_program_via_python_bytecode,
)
from native_vm import (
    NamespaceRef as NativeNamespaceRef,
    NativeVM,
)
from pathlib import (
    Path,
)
from stdlib import (
    register_stdlib,
)
from tiny_errors import (
    SourcePos,
    SourceSpan,
    StackFrame,
    _line_info,
)
from tiny_language_api import (
    LLVMModuleInfo,
    LLVMModuleResolver,
    NativeModuleResolver,
    _CaptureCStdout,
    _LLVMPythonInterop,
    _LLVM_PYTHON_INTEROP,
    _compiler_opt_args,
    _configure_readline,
    _copy_on_call_default,
    _create_llvm_engine,
    _emit_native_diagnostics,
    _experimental_math_formula_enabled,
    _experimental_math_tuples_enabled,
    _find_repo_root,
    _flush_c_stdout,
    _format_compiler_failure,
    _format_error_for_source,
    _format_llvm_debug_context,
    _heap_lints_enabled,
    _is_incomplete_source,
    _load_llvmlite_binding,
    _maybe_add_llvm_pass,
    _merge_llvm_programs,
    _message_has_source_context,
    _module_namespace_for_path,
    _optimize_llvm_ir,
    _optimize_llvm_module,
    _parse_and_lint,
    _parse_with_tiny_parser,
    _print_optional_dependency_instructions,
    _raise_llvm_jit_error,
    _read_repl_command,
    _register_llvm_symbols,
    _repl_highlighting_enabled,
    _resolve_llvm_opt_level,
    _resolve_llvm_target_info,
    _resolve_read_fn,
    _save_history,
    _strip_inline_location,
    _tiny_get_field,
    _tiny_heap_value,
    _tiny_parser_bootstrap_source,
    _tiny_to_dict,
    _tiny_to_list,
    _tiny_to_pairs,
    _tiny_to_pos,
    _tiny_to_python_ast,
    _tiny_to_set,
    _tiny_to_span,
    _use_tiny_parser,
    _v1_only_enabled,
    compile_and_run,
    compile_to_c_executable,
    compile_to_c_source,
    compile_to_executable,
    compile_to_llvm_bitcode_via_c,
    compile_to_llvm_ir,
    compile_to_llvm_ir_via_c,
    compile_to_python_ast,
    compile_to_python_source,
    main,
    run_file,
    run_with_llvm_jit,
    run_with_native_backend,
    run_with_python_backend,
    run_with_python_bytecode_backend,
)
from tiny_language_ast import (
    Assign,
    Await,
    Bin,
    Bool,
    Call,
    CallStmt,
    ClassDef,
    ClassNew,
    DestructAssign,
    Field,
    FieldAssign,
    Flush,
    Fn,
    IR,
    If,
    Import,
    Let,
    Match,
    MatchCase,
    MethodCall,
    MethodDef,
    Namespace,
    New,
    NewLit,
    Null,
    Num,
    ObjLit,
    OpDef,
    Param,
    Pattern,
    Print,
    Return,
    Spawn,
    Str,
    Switch,
    SwitchCase,
    TaskBlock,
    TryCatch,
    TypeDef,
    TypeVariant,
    Var,
    VariantCtor,
    VariantPattern,
    While,
    WildcardPattern,
)
from tiny_language_codegen_c import (
    CCodeGenerator,
    _FunctionBlock,
    _ProgramLayout,
)
from tiny_language_codegen_llvm import (
    LLVMCodeGenerator,
    _ResolvedFunctionSignature,
    _StackValue,
    _TypeValue,
)
from tiny_language_codegen_native import (
    NativeCodeGenerator,
)
from tiny_language_codegen_py import (
    PythonCodeGenerator,
)
from tiny_language_error_codes import (
    _closest_match as _closest_match_impl,
    classify_error,
)
from tiny_language_eval import (
    ReturnSignal,
    _ALLOWED_CALL_PREFIXES,
    _SpawnCancelled,
    _block_returns_value,
    _call_stmt_allowed,
    _fn_returns_value,
    _prefer_named_span,
    _return_type_is_void,
    _span_or_pos,
    eval_block,
    eval_expr,
    eval_stmt,
)
from tiny_language_highlighting import (
    PYGMENTS_AVAILABLE,
    highlight_source,
)
from tiny_language_lexer import (
    BUILTINS,
    KEYWORDS,
    Lexer,
    Token,
)
from tiny_language_linter import (
    _AnnotationIndex,
    _ClassInfo,
    _FunctionSignature,
    _HeapLifetime,
    _INT_LITERAL,
    _ModuleSummary,
    _TypeInfo,
    _base_type_name,
    _block_guarantees_exit,
    _block_guarantees_return,
    _build_variant_type_index,
    _clone_heap_sizes,
    _clone_heap_states,
    _collect_annotation_index,
    _collect_function_return_values,
    _collect_function_signatures,
    _collect_names_in_expr,
    _format_signature,
    _format_summary_params,
    _format_type_expression,
    _function_returns_value,
    _heap_allocation_size,
    _heap_pointer_name,
    _implicit_any_warning,
    _import_binding_name,
    _infer_expr_type,
    _infer_list_literal_type,
    _infer_typed_expr_type,
    _int_literal,
    _is_heap_allocation_expr,
    _is_optional_annotation,
    _iter_imports,
    _lint_error,
    _lint_heap_bounds_call,
    _lint_heap_bounds_expr,
    _lint_heap_expr,
    _load_import_summaries,
    _merge_heap_sizes,
    _merge_heap_states,
    _module_has_annotations,
    _narrow_env_for_condition,
    _node_pos,
    _node_span,
    _normalize_inferred_type,
    _null_guarded_binding,
    _param_names,
    _parse_module_summary,
    _parse_type_expression,
    _pattern_bindings,
    _qualify_name,
    _qualify_reference,
    _render_type_expression,
    _resolve_field_type,
    _resolve_import_name,
    _resolve_method_params,
    _resolve_method_return,
    _return_signature,
    _signature_has_annotations,
    _split_summary_params,
    _stmt_guarantees_exit,
    _summary_paths_for_module,
    _type_name_matches,
    _types_match,
    _variant_info_for_pattern,
    build_module_summary,
    check_destruct_call_expr,
    lint_annotation_enforcement,
    lint_assignment_types,
    lint_bare_call_results,
    lint_call_validation,
    lint_destruct_call_outputs,
    lint_destruct_call_outputs_stmt,
    lint_fn_params_used,
    lint_heap_lifetimes,
    lint_implicit_any_usage,
    lint_import_style,
    lint_inferred_return_types,
    lint_locals_used,
    lint_method_params_used,
    lint_no_consecutive_definitions,
    lint_no_underscore_bindings,
    lint_param_mutations_returned,
    lint_return_exhaustiveness,
    lint_return_signatures,
    lint_return_validation,
    lint_stmt_reads,
    lint_unreachable_code,
    uses_in_expr,
)
from tiny_language_module_resolution import (
    ModuleResolutionConfig,
    candidate_module_paths,
    resolve_module_name,
)
from tiny_language_parser import (
    Parser,
)
from tiny_language_preamble import (
    TinyLangError,
    _FallbackReadline,
    _HAS_TERMIOS,
    _classify_error,
    _closest_match,
    _load_readline,
    format_error,
    readline,
    termios,
    tty,
)
from tiny_language_runtime import (
    BaseView,
    CancellationToken,
    Debugger,
    LOGGER,
    ModuleResolver,
    NamespaceRef,
    ParamKey,
    ParameterBinding,
    Runtime,
    SpawnHandle,
    TaskScope,
    _ParsedType,
)
from tiny_language_runtime_debugger import (
    DebugSnapshot,
    ScopeSnapshot,
    StepRequest,
)
from tiny_language_runtime_environment import (
    Environment,
)
from tiny_pkg_cli import (
    main as pkg_main,
)
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from tiny_language_api import __all__


if __name__ == "__main__":
    raise SystemExit(main())
