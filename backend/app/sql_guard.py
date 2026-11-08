import re

import pglast
from pglast import parse_sql
from pglast.visitors import Visitor

from .errors import ApiError

FORBIDDEN_ROOTS = (
    "InsertStmt", "UpdateStmt", "DeleteStmt", "MergeStmt", "CreateStmt", "CreateTableAsStmt",
    "CreateTableStmt", "DropStmt", "AlterTableStmt", "TruncateStmt", "GrantStmt", "CopyStmt",
    "VariableSetStmt", "VariableShowStmt", "TransactionStmt", "DoStmt", "CallStmt",
    "CreateDomainStmt", "DefineStmt", "IndexStmt", "ViewStmt", "RenameStmt", "CommentStmt",
    "VacuumStmt", "RefreshMatViewStmt", "LockStmt", "PrepareStmt", "ExecuteStmt", "DeallocateStmt",
    "DiscardStmt", "ClosePortalStmt", "FetchStmt", "ListenStmt", "NotifyStmt", "UnlistenStmt",
    "SecLabelStmt", "CheckPointStmt", "ReindexStmt", "ClusterStmt",
)

FORBIDDEN_NODES = {
    "InsertStmt", "UpdateStmt", "DeleteStmt", "MergeStmt", "CreateStmt", "CreateTableAsStmt",
    "DropStmt", "AlterTableStmt", "TruncateStmt", "GrantStmt", "CopyStmt", "VariableSetStmt",
    "VariableShowStmt", "TransactionStmt", "DoStmt", "CallStmt", "DefineStmt", "IndexStmt",
    "ViewStmt", "RenameStmt", "VacuumStmt", "RefreshMatViewStmt", "LockStmt", "PrepareStmt",
    "ExecuteStmt", "DiscardStmt", "ListenStmt", "NotifyStmt", "SecLabelStmt", "CheckPointStmt",
    "ReindexStmt", "ClusterStmt", "CreateDomainStmt", "CommentStmt", "AlterDomainStmt",
    "AlterDefaultPrivilegesStmt", "AlterEnumStmt", "AlterExtensionStmt", "AlterFdwStmt",
    "AlterForeignServerStmt", "AlterFunctionStmt", "AlterObjectDependsStmt",
    "AlterObjectSchemaStmt", "AlterOwnerStmt", "AlterPolicyStmt", "AlterRoleStmt",
    "AlterRoleSetStmt", "AlterSeqStmt", "AlterSystemStmt", "AlterTSConfigurationStmt",
    "AlterTSDictionaryStmt", "AlterTableMoveAllStmt", "AlterUserMappingStmt",
    "CreateAssertionStmt", "CreateForeignServerStmt", "CreateForeignTableStmt",
    "CreateFdwStmt", "CreateFunctionStmt", "CreateOpClassStmt", "CreateOpFamilyStmt",
    "CreatePLangStmt", "CreatePolicyStmt", "CreatePublicationStmt", "CreateRoleStmt",
    "CreateSchemaStmt", "CreateSequenceStmt", "CreateStatsStmt", "CreateTransformStmt",
    "CreateTrigStmt", "CreateUserMappingStmt", "DeallocateStmt", "DeclareCursorStmt",
    "DropdbStmt", "ReassignOwnedStmt", "ReplicaIdentityStmt",
}

FORBIDDEN_FUNCTIONS = {
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "dblink", "dblink_exec", "dblink_connect",
    "dblink_disconnect", "dblink_build_sql_insert", "lo_import", "lo_export", "lo_get",
    "lo_put", "lo_from_bytea", "pg_read_file", "pg_read_binary_file", "pg_write_file",
    "set_config", "pg_advisory_lock", "pg_advisory_unlock", "pg_advisory_xact_lock",
    "pg_advisory_lock_shared", "pg_try_advisory_lock", "pg_terminate_backend",
    "pg_cancel_backend", "pg_reload_conf", "pg_ls_dir", "pg_stat_file",
}

# Substrings that must not appear even inside string literals/comments of the LLM SQL:
# belt-and-braces on top of the AST checks.
_DENYLIST_RE = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in sorted(FORBIDDEN_FUNCTIONS)) + r")\s*\(",
    re.IGNORECASE,
)


class _Checker(Visitor):
    def __init__(self):
        super().__init__()
        self.functions: set[str] = set()
        self.has_into = False
        self.has_locking = False

    def visit(self, ancestors, node):
        name = type(node).__name__
        if name in FORBIDDEN_NODES:
            raise ApiError(400, "SQL_NOT_SELECT", "SQL содержит запрещённую команду.")
        if isinstance(node, pglast.ast.SelectStmt):
            if node.intoClause is not None:
                raise ApiError(400, "SQL_NOT_SELECT", "SELECT INTO запрещён.")
            if node.lockingClause:
                raise ApiError(400, "SQL_NOT_SELECT", "FOR UPDATE/SHARE запрещён.")
        if isinstance(node, pglast.ast.CommonTableExpr):
            if type(node.ctequery).__name__ not in ("SelectStmt",):
                raise ApiError(400, "SQL_NOT_SELECT", "Изменяющие CTE запрещены.")
        if isinstance(node, pglast.ast.FuncCall):
            for part in node.funcname:
                fname = getattr(part, "sval", None)
                if fname:
                    self.functions.add(fname.lower())
        if isinstance(node, pglast.ast.A_Const):
            val = node.val
            sval = getattr(val, "sval", None) if val is not None else None
            if isinstance(sval, str) and _DENYLIST_RE.search(sval):
                raise ApiError(400, "SQL_NOT_SELECT", "SQL содержит запрещённую функцию.")


def validate_sql(sql: str) -> str:
    if not sql or not sql.strip():
        raise ApiError(400, "VALIDATION_ERROR", "Пустой SQL.")
    try:
        statements = parse_sql(sql)
    except pglast.parser.ParseError:
        raise ApiError(400, "SQL_NOT_SELECT", "SQL не разобран как корректный PostgreSQL запрос.")

    if len(statements) != 1:
        raise ApiError(400, "SQL_MULTIPLE_STATEMENTS", "Допускается ровно один SQL-запрос.")

    root = statements[0].stmt
    if type(root).__name__ in FORBIDDEN_ROOTS:
        raise ApiError(400, "SQL_NOT_SELECT", "Допустимы только SELECT-запросы.")
    if not _is_select_tree(root):
        raise ApiError(400, "SQL_NOT_SELECT", "Допустимы только SELECT-запросы.")

    checker = _Checker()
    checker(root)
    for fname in checker.functions:
        if fname in FORBIDDEN_FUNCTIONS:
            raise ApiError(400, "SQL_NOT_SELECT", f"Функция {fname} запрещена.")

    return sql.strip().rstrip(";").strip()


def _is_select_tree(node) -> bool:
    if isinstance(node, pglast.ast.SelectStmt):
        return _is_select_tree(node.larg) if node.larg is not None else True
    return False
