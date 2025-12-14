from __future__ import annotations
import os
import glob
from enum import Enum
import tree_sitter_c_sharp
from tree_sitter import Language, Parser, Node, Tree

# TODO nested classes:
# ERR: type AiState not found
# ERR: type SummaryMode not found


# https://stackoverflow.com/questions/1175208/
def camel_to_snake(s: str) -> str:
    return "".join(["_" + c.lower() if c.isupper() else c for c in s]).lstrip("_")


class NodeKind(Enum):
    CLASS_DECLARATION = "class_declaration"
    IFACE_DECLARATION = "interface_declaration"
    STRUCT_DECLARATION = "struct_declaration"
    ENUM_DECLARATION = "enum_declaration"
    ENUM_DECLARATION_LIST = "enum_member_declaration_list"
    ENUM_MEMBER_DECLARATION = "enum_member_declaration"
    QUALIFIED_NAME = "qualified_name"
    FILE_NAMESPACE = "file_scoped_namespace_declaration"
    IDENTIFIER = "identifier"
    INT_LITERAL = "integer_literal"
    DECLARATION_LIST = "declaration_list"
    FIELD_DECLARATION = "field_declaration"
    USING_DIRECTIVE = "using_directive"
    PREDEFINED_TYPE = "predefined_type"
    NULLABLE_TYPE = "nullable_type"
    TUPLE_TYPE = "tuple_type"
    GENERIC_NAME = "generic_name"
    ARRAY_TYPE = "array_type"
    VARIABLE_DECLARATION = "variable_declaration"
    VARIABLE_DECLARATOR = "variable_declarator"
    TYPE_ARG_LIST = "type_argument_list"
    TYPE_PARAM_LIST = "type_parameter_list"
    TYPE_PARAM = "type_parameter"


class CodeIdentifier:
    def __init__(self, name: str, id: str = ""):
        self.id = id if id else name
        self.name = name


class CodeParam(CodeIdentifier):
    def __init__(self, name: str, type: CodeClass, default_value: str):
        super().__init__(name)
        self.type = type
        self.default_value = default_value


class CodeMethod(CodeIdentifier):
    def __init__(self, name: str, type: CodeClass, is_extension: bool, body_node: Node):
        super().__init__(name)
        self.type = type
        self.is_extension = is_extension
        self.generic_params: list[CodeClass] = []
        self.params: list[CodeParam] = []
        self.body_node = body_node


class CodeField(CodeIdentifier):
    def __init__(self, name: str, type: CodeType):
        super().__init__(name)
        self.type = type

    def get_declaration(self) -> str:
        return f"{self.type.name} {self.name};"


class CodeProperty(CodeIdentifier):
    def __init__(
        self, name: str, type: CodeClass, setter: CodeMethod, getter: CodeMethod
    ):
        super().__init__(name)
        self.type = type
        self.setter = setter
        self.getter = getter


class CodeClassKind(Enum):
    CLASS = 1
    STRUCT = 2
    INTERFACE = 3


class CodeType(CodeIdentifier):
    def __init__(self, name: str, id: str, parent_type_scope: CodeTypeScope):
        super().__init__(name, id)
        self.parent_type_scope = parent_type_scope
        parent_type_scope.types_by_id[id] = self

    def is_dummy(self) -> bool:
        raise NotImplementedError("CodeType.is_dummy()")

    def is_emmittable(self) -> bool:
        return not self.is_dummy()

    def get_forward_declaration(self) -> str:
        raise NotImplementedError("CodeType.get_forward_declaration()")

    def get_header_contents(self) -> str:
        raise NotImplementedError("CodeType.get_header_contents()")

    def emit_cpp(self, path: str):
        if self.is_emmittable():
            with open(f"{path}/{camel_to_snake(self.name)}.hpp", "w") as out_file:
                out_file.write(self.get_header_contents())

    def get_include_path(self) -> str:
        assert isinstance(self.parent_type_scope, CodeNamespace)
        return f"{self.parent_type_scope.get_directory_path()}/{camel_to_snake(self.name)}.hpp"


class CodeNullableType(CodeType):
    def __init__(self, base_type):
        super().__init__(
            base_type.name + "?", base_type.id + "?", base_type.parent_type_scope
        )
        self.base_type = base_type
        # print(f"Found nullable type {self.name}")

    def is_dummy(self) -> bool:
        return False

    def is_emmittable(self) -> bool:
        return False


class DummyType(CodeType):
    def __init__(self, name: str, parent_type_scope: CodeTypeScope):
        super().__init__(name=name, id=name, parent_type_scope=parent_type_scope)

    def is_dummy(self):
        return True


class CodeTypeScope:
    def __init__(self: CodeTypeScope):
        self.types_by_id: dict[str, CodeType] = {}


class CodeClassSpecialized(CodeType):
    def __init__(self, generic_class: CodeClass, type_params: list[CodeType]):
        name = f"{generic_class.name}<{', '.join(t.name for t in type_params)}>"
        super().__init__(
            name=name,
            id=name,
            parent_type_scope=generic_class.parent_type_scope,
        )
        self.generic_class = generic_class
        self.type_params = type_params
        # print(f"Found generic class specialization: {self.name}")

    def is_dummy(self):
        return self.generic_class.is_dummy()

    def is_emmittable(self) -> bool:
        return False


class ClassNodeContext:
    def __init__(
        self,
        declaration_list_node: Node,
        parent_namespace: CodeNamespace,
        using_strs: list[str],
    ):
        self.declaration_list_node = declaration_list_node
        self.parent_namespace = parent_namespace
        self.using_strs = using_strs


class CodeGenericParameter(CodeType):
    def __init__(self, name: str, parent_class: CodeClass):
        super().__init__(name, name, parent_class)

    def is_dummy(self) -> bool:
        return False

    def is_emmittable(self) -> bool:
        return False


class CodeClass(CodeType, CodeTypeScope):
    @staticmethod
    def get_id(name: str, param_count: int) -> str:
        id = f"{name}`{param_count}" if param_count else name
        return id

    def __init__(
        self,
        name: str,
        kind: CodeClassKind,
        generic_parameter_names: list[str],
        parent_namespace: CodeNamespace,
    ):
        id = CodeClass.get_id(name, len(generic_parameter_names))
        CodeType.__init__(self, name, id, parent_namespace)
        CodeTypeScope.__init__(self)

        self.kind = kind
        self.is_dummy_type = False
        self.ancestors: list[CodeClass] = []
        self.properties: list[CodeProperty] = []
        self.fields: dict[str, CodeField] = {}
        self.methods: list[CodeMethod] = []
        self.usings: list[CodeNamespace] = []
        for gn in generic_parameter_names:
            self.types_by_id[gn] = CodeGenericParameter(gn, self)

        self.contexts: list[ClassNodeContext] = []

    def is_dummy(self):
        return self.is_dummy_type

    def get_template_declaration(self) -> str:
        if len(self.types_by_id):
            return f"template<{', '.join(f'typename {t}' for t in self.types_by_id)}>"
        return ""

    def get_forward_declaration(self) -> str:
        template_decl = self.get_template_declaration()
        if template_decl:
            template_decl += " "
        return f"{template_decl}class {self.name};"

    def get_header_contents(self) -> str:
        assert isinstance(self.parent_type_scope, CodeNamespace)

        out = "#pragma once\n\n"

        parent_ns: CodeNamespace | None = self.parent_type_scope
        while parent_ns and parent_ns.name != "":
            out += f"#include <{parent_ns.get_header_path()}>\n"
            parent_ns = parent_ns.parent
        out += "\n"

        for using in self.usings:
            out += f"#include <{using.get_header_path()}>\n"
        out += "\n"

        ns_name = self.parent_type_scope.get_full_path().replace(".", "::")
        out += f"namespace {ns_name} {{\n\n"

        for using in self.usings:
            out += f"using namespace {using.get_full_path().replace('.','::')};\n"
        out += "\n"

        template_decl = self.get_template_declaration()
        if template_decl:
            template_decl += "\n"
        out += f"{template_decl}class {self.name} {{\n"
        out += "public:\n"

        for field in self.fields.values():
            out += f"\t{field.get_declaration()}\n"

        out += f"}};\n\n"
        out += f"}} // namespace {ns_name}\n"
        return out


class CodeEnumEntry(CodeIdentifier):
    def __init__(self, name: str, value: str | None):
        super().__init__(name)
        self.value = value


class CodeEnum(CodeType):
    def __init__(self, name: str, parent_namespace: CodeNamespace):
        super().__init__(name=name, id=name, parent_type_scope=parent_namespace)
        self.entries: list[CodeEnumEntry] = []

    def is_dummy(self):
        return False

    def get_forward_declaration(self) -> str:
        return f"enum class {self.name};"

    def get_header_contents(self) -> str:
        assert isinstance(self.parent_type_scope, CodeNamespace)

        out = "#pragma once\n\n"
        ns_name = self.parent_type_scope.get_full_path().replace(".", "::")
        out += f"namespace {ns_name} {{\n\n"
        out += f"enum class {self.name} {{\n"

        for entry in self.entries:
            value_str = f" = {entry.value}" if entry.value else ""
            out += f"\t{entry.name}{value_str},\n"

        out += f"}};\n\n"
        out += f"}} // namespace {ns_name}\n"
        return out


class CodeNamespace(CodeIdentifier, CodeTypeScope):
    def __init__(self, name: str, parent: CodeNamespace | None):
        CodeIdentifier.__init__(self, name)
        CodeTypeScope.__init__(self)
        self.parent = parent
        self.subnamespaces: dict[str, CodeNamespace] = {}

        if parent:
            parent.subnamespaces[name] = self

    def get_full_path(self) -> str:
        full_namespace = self.name
        parent = self.parent
        while parent and parent.name:
            full_namespace = f"{parent.name}.{full_namespace}"
            parent = parent.parent
        return full_namespace

    def get_directory_path(self) -> str:
        dir_path = camel_to_snake(self.name)
        parent = self.parent
        while parent and parent.name:
            dir_path = f"{camel_to_snake(parent.name)}/{dir_path}"
            parent = parent.parent
        return dir_path

    def get_header_path(self) -> str:
        return f"{self.get_directory_path()}/namespace.hpp"

    def get_all_types(self) -> list[CodeType]:
        types = []
        for type in self.types_by_id.values():
            types.append(type)
        for child_name in self.subnamespaces:
            types += self.subnamespaces[child_name].get_all_types()
        return types

    def emit_cpp(self, path: str):
        os.makedirs(path, exist_ok=True)
        with open(f"{path}/namespace.hpp", "w") as out_file:
            out_file.write(self.get_namespace_header())
        for subnamespace in self.subnamespaces.values():
            subnamespace.emit_cpp(f"{path}/{camel_to_snake(subnamespace.name)}")

        for type in self.types_by_id.values():
            type.emit_cpp(f"{path}")

    def get_namespace_header(self) -> str:
        ns_name = self.get_full_path().replace(".", "::")
        out = "#pragma once\n\n"

        out += f"namespace {ns_name} {{\n\n"
        for type in self.types_by_id.values():
            if type.is_emmittable():
                out += f"{type.get_forward_declaration()}\n"
        out += f"\n}} // namespace {ns_name}\n\n"

        for type in self.types_by_id.values():
            if type.is_emmittable():
                out += f"#include <{type.get_include_path()}>\n"
        out += "\n"
        return out


class Codebase:
    def __init__(self):
        self.global_namespace = CodeNamespace(name="", parent=None)

    def get_all_types(self) -> list[CodeType]:
        return self.global_namespace.get_all_types()

    def get_namespace(self, namespace_path: str) -> CodeNamespace:
        if namespace_path == "":
            return self.global_namespace

        parts = namespace_path.split(".")
        ns = self.global_namespace
        for part in parts:
            ns = ns.subnamespaces[part]
        return ns

    def resolve_type(
        self,
        type_id: str,
        namespaces: list[CodeNamespace],
        parent_class: CodeClass | None,
    ) -> CodeType | None:
        if parent_class and len(parent_class.types_by_id):
            if type_id in parent_class.types_by_id:
                return parent_class.types_by_id[type_id]

        for namespace in namespaces:
            if type_id in namespace.types_by_id:
                return namespace.types_by_id[type_id]

        print(f"ERR: type {type_id} not found")
        return None

    def emit_cpp(self, path: str):
        self.global_namespace.emit_cpp(path)


def parse_files(root_path: str) -> dict[str, Tree]:
    LANG_CSHARP = Language(tree_sitter_c_sharp.language())
    parser = Parser(LANG_CSHARP)

    paths = glob.glob(f"{root_path}/**/*.cs", recursive=True)
    trees_by_path: dict[str, Tree] = {}
    for path in paths:
        file_bytes = open(path).read().encode()
        tree = parser.parse(file_bytes)
        trees_by_path[path] = tree
    return trees_by_path


def find_node_by_grammar_name(node: Node, grammar_name: str) -> Node | None:
    if node.grammar_name == grammar_name:
        return node
    found_node: Node | None = None
    for child in node.named_children:
        found_node = find_node_by_grammar_name(child, grammar_name)
        if found_node:
            break
    return found_node


def get_using_from_node(node: Node) -> str:
    assert node.named_children[0].grammar_name in [
        NodeKind.QUALIFIED_NAME.value,
        NodeKind.IDENTIFIER.value,
    ]
    assert node.named_children[0].text

    return node.named_children[0].text.decode()


def get_or_create_namespace_from_node(node: Node, codebase: Codebase) -> CodeNamespace:
    first_child = node.named_children[0]
    assert first_child.grammar_name == NodeKind.QUALIFIED_NAME.value
    assert first_child.text
    namespace_chain = first_child.text.decode().split(".")
    parent_namespace = codebase.global_namespace
    for segment_name in namespace_chain:
        if segment_name not in parent_namespace.subnamespaces:
            ns = CodeNamespace(segment_name, parent_namespace)
            parent_namespace = ns
        else:
            parent_namespace = parent_namespace.subnamespaces[segment_name]
    return parent_namespace


def get_type_parameter_names_from_node(node: Node) -> list[str]:
    param_names: list[str] = []
    for child in node.named_children:
        if child.grammar_name == NodeKind.TYPE_PARAM.value:
            assert child.named_children[0]
            identifier_node = child.named_children[0]
            assert identifier_node.grammar_name == NodeKind.IDENTIFIER.value
            assert identifier_node.text
            param_names.append(identifier_node.text.decode())

    return param_names


def get_or_create_class_from_node(
    node: Node, namespace: CodeNamespace, usings: list[str]
):
    match node.grammar_name:
        case NodeKind.CLASS_DECLARATION.value:
            kind = CodeClassKind.CLASS
        case NodeKind.IFACE_DECLARATION.value:
            kind = CodeClassKind.INTERFACE
        case NodeKind.STRUCT_DECLARATION.value:
            kind = CodeClassKind.STRUCT

    param_names: list[str] = []
    was_identifier = False
    for child in node.named_children:
        if child.grammar_name == NodeKind.IDENTIFIER.value:
            assert not was_identifier
            assert child.text
            class_name = child.text.decode()
            was_identifier = True
        elif child.grammar_name == NodeKind.TYPE_PARAM_LIST.value:
            param_names = get_type_parameter_names_from_node(child)

    class_id = class_name
    if len(param_names):
        class_id += f"`{len(param_names)}"

    assert class_name
    if class_id not in namespace.types_by_id:
        code_class = CodeClass(class_name, kind, param_names, namespace)
        # print(
        #     f"Found {kind.name.lower()} {class_name} in namespace {namespace.get_full_path()}"
        # )
    else:
        found_type = namespace.types_by_id[class_id]
        assert isinstance(found_type, CodeClass)
        code_class = found_type

    declaration_list_node = find_node_by_grammar_name(
        node, NodeKind.DECLARATION_LIST.value
    )
    assert declaration_list_node
    code_class.contexts.append(
        ClassNodeContext(declaration_list_node, namespace, usings)
    )


def parse_enum_declaration_list(enum: CodeEnum, declaration_list_node: Node):
    for member_declaration in declaration_list_node.named_children:
        assert member_declaration.grammar_name == NodeKind.ENUM_MEMBER_DECLARATION.value
        name_node = member_declaration.named_children[0]
        assert name_node.grammar_name == NodeKind.IDENTIFIER.value
        assert name_node.text
        value_text: str | None = None
        if len(member_declaration.named_children) > 1:
            value_node = member_declaration.named_children[1]
            assert value_node.text
            value_text = value_node.text.decode()
        enum.entries.append(CodeEnumEntry(name_node.text.decode(), value_text))


def get_or_create_enum_from_node(node: Node, namespace: CodeNamespace) -> CodeEnum:
    assert node.grammar_name == NodeKind.ENUM_DECLARATION.value
    enum_name: str | None = None
    declaration_list_node: Node | None = None
    for child in node.named_children:
        if child.grammar_name == NodeKind.IDENTIFIER.value:
            assert child.text
            if not enum_name:
                enum_name = child.text.decode()
        elif child.grammar_name == NodeKind.ENUM_DECLARATION_LIST.value:
            declaration_list_node = child

    assert enum_name
    if enum_name not in namespace.types_by_id:
        code_enum = CodeEnum(enum_name, namespace)
        if declaration_list_node:
            parse_enum_declaration_list(code_enum, declaration_list_node)
        # print(f"Found enum {enum_name} in namespace {namespace.get_full_path()}")
    else:
        found_type = namespace.types_by_id[enum_name]
        assert isinstance(found_type, CodeEnum)
        code_enum = found_type
    return code_enum


def get_generic_type_from_node(
    codebase: Codebase,
    type_node: Node,
    namespaces: list[CodeNamespace],
    parent_class: CodeClass,
) -> CodeType:
    generic_type_name_node = type_node.named_children[0]
    assert generic_type_name_node.grammar_name == NodeKind.IDENTIFIER.value
    assert generic_type_name_node.text
    generic_type_name = generic_type_name_node.text.decode()

    type_arg_list_node = type_node.named_children[1]
    assert type_arg_list_node.grammar_name == NodeKind.TYPE_ARG_LIST.value
    generic_args: list[CodeType] = []
    for arg_node in type_arg_list_node.named_children:
        generic_args.append(
            get_type_from_node(codebase, arg_node, namespaces, parent_class)
        )

    generic_type_id = CodeClass.get_id(generic_type_name, len(generic_args))
    generic_type = codebase.resolve_type(generic_type_id, namespaces, parent_class)
    assert generic_type
    assert isinstance(generic_type, CodeClass)
    type = CodeClassSpecialized(generic_type, generic_args)
    return type


def get_array_type_from_node(
    codebase: Codebase,
    type_node: Node,
    namespaces: list[CodeNamespace],
    parent_class: CodeClass,
) -> CodeType:
    assert len(type_node.named_children) == 2
    element_type_node = type_node.named_children[0]
    element_type = get_type_from_node(
        codebase,
        element_type_node,
        namespaces,
        parent_class,
    )

    array_rank_node = type_node.named_children[1]
    assert array_rank_node.text
    assert array_rank_node.text.decode() == "[]", "Unsupported non-1D array"

    generic_type_id = CodeClass.get_id("List", 1)
    generic_type = codebase.resolve_type(
        generic_type_id,
        namespaces + [codebase.get_namespace("System.Collections.Generic")],
        parent_class,
    )
    assert generic_type
    assert isinstance(generic_type, CodeClass)

    type = CodeClassSpecialized(
        generic_type,
        [element_type],
    )
    return type


def get_type_from_node(
    codebase: Codebase,
    type_node: Node,
    namespaces: list[CodeNamespace],
    parent_class: CodeClass,
) -> CodeType:
    type: CodeType
    match type_node.grammar_name:
        case NodeKind.TUPLE_TYPE.value:
            raise Exception("Tuple types aren't supported")

        case NodeKind.GENERIC_NAME.value:
            type = get_generic_type_from_node(
                codebase, type_node, namespaces, parent_class
            )

        case NodeKind.ARRAY_TYPE.value:
            type = get_array_type_from_node(
                codebase, type_node, namespaces, parent_class
            )

        case NodeKind.IDENTIFIER.value | NodeKind.PREDEFINED_TYPE.value:
            assert type_node.text
            type_id = type_node.text.decode()
            resolved_type = codebase.resolve_type(type_id, namespaces, parent_class)
            if not resolved_type:
                # TODO: replace with assert after implementing nested class
                resolved_type = DummyType(type_id, parent_class.parent_type_scope)
            type = resolved_type

        case NodeKind.NULLABLE_TYPE.value:
            assert type_node.text
            assert type_node.named_child_count == 1
            child_node = type_node.named_children[0]
            base_type = get_type_from_node(
                codebase, child_node, namespaces, parent_class
            )
            type = CodeNullableType(base_type)

    return type


def create_class_field(
    classlike: CodeClass, node: Node, namespaces: list[CodeNamespace]
) -> CodeField:
    declaration_node = find_node_by_grammar_name(
        node, NodeKind.VARIABLE_DECLARATION.value
    )
    assert declaration_node
    type_node = declaration_node.named_children[0]
    declarator_node = declaration_node.named_children[1]

    field_type = get_type_from_node(codebase, type_node, namespaces, classlike)

    assert declarator_node.grammar_name == NodeKind.VARIABLE_DECLARATOR.value
    name_node = declarator_node.named_children[0]
    assert name_node.grammar_name == NodeKind.IDENTIFIER.value

    assert name_node.text
    field_name = name_node.text.decode()
    field = CodeField(field_name, field_type)
    classlike.fields[field.name] = field
    # print(f"Added field {classlike.name}.{field.name} of type {field_type.name}")
    return field


def traverse_tree_level(
    parent_node: Node, codebase: Codebase, namespace: CodeNamespace, usings: list[str]
):
    for child_node in parent_node.named_children:
        match child_node.grammar_name:
            case NodeKind.USING_DIRECTIVE.value:
                usings.append(get_using_from_node(child_node))
            case NodeKind.FILE_NAMESPACE.value:
                namespace = get_or_create_namespace_from_node(child_node, codebase)
            case (
                NodeKind.CLASS_DECLARATION.value
                | NodeKind.IFACE_DECLARATION.value
                | NodeKind.STRUCT_DECLARATION.value
            ):
                get_or_create_class_from_node(child_node, namespace, usings)
            case NodeKind.ENUM_DECLARATION.value:
                get_or_create_enum_from_node(child_node, namespace)


def gather_namespace_and_types(trees_by_path: dict[str, Tree], codebase: Codebase):
    for path in trees_by_path:
        tree = trees_by_path[path]
        namespace = codebase.global_namespace
        traverse_tree_level(tree.root_node, codebase, namespace, [])


def gather_class_elements(codebase: Codebase):
    classlikes = [t for t in codebase.get_all_types() if isinstance(t, CodeClass)]
    print(f"Got {len(classlikes)} class-likes")
    for classlike in classlikes:
        for context in classlike.contexts:

            namespaces: list[CodeNamespace] = []

            # Use parent namespace and all of its direct parents
            ns: CodeNamespace | None = context.parent_namespace
            while ns and ns != codebase.global_namespace:
                namespaces.append(ns)
                ns = ns.parent

            # After that's exhausted, use specific namespaces from `using`s
            namespaces += [codebase.get_namespace(ns) for ns in context.using_strs]
            namespaces += [codebase.global_namespace]

            for declaration_node in context.declaration_list_node.named_children:
                match declaration_node.grammar_name:
                    case NodeKind.FIELD_DECLARATION.value:
                        create_class_field(classlike, declaration_node, namespaces)


def consolidate_class_usings(codebase: Codebase):
    classlikes = [t for t in codebase.get_all_types() if isinstance(t, CodeClass)]
    print(f"Got {len(classlikes)} class-likes")
    for classlike in classlikes:
        for context in classlike.contexts:
            for using in context.using_strs:
                ns = codebase.get_namespace(using)
                if ns not in classlike.usings:
                    classlike.usings.append(ns)


def prepare_out_directory(out_path: str):
    if os.path.exists(out_path):
        old_out_files = glob.glob(f"{out_path}/**/*.cs")
        for f in old_out_files:
            os.remove(f)
    else:
        os.makedirs(out_path, exist_ok=True)


def populate_with_dummy(codebase: Codebase):
    def make_dummy_generic(name: str, param_names: list[str], namespace: CodeNamespace):
        dummy = CodeClass(name, CodeClassKind.CLASS, param_names, namespace)
        dummy.is_dummy_type = True

    def make_dummy_class(name, namespace):
        dummy = CodeClass(name, CodeClassKind.CLASS, [], namespace)
        dummy.is_dummy_type = True

    ns_system = CodeNamespace("System", codebase.global_namespace)
    ns_system_linq = CodeNamespace("Linq", ns_system)
    ns_system_collections = CodeNamespace("Collections", ns_system)
    ns_system_collections_generic = CodeNamespace("Generic", ns_system_collections)
    ns_system_io = CodeNamespace("IO", ns_system)
    ns_system_text = CodeNamespace("Text", ns_system)
    ns_system_text_regularexpressions = CodeNamespace(
        "RegularExpressions", ns_system_text
    )
    ns_godot = CodeNamespace("Godot", codebase.global_namespace)
    ns_gdunit4 = CodeNamespace("GdUnit4", codebase.global_namespace)
    ns_gdunit4_assertions = CodeNamespace("Assertions", ns_gdunit4)

    make_dummy_generic("HashSet", ["TElement"], ns_system_collections_generic)
    make_dummy_generic("List", ["TElement"], ns_system_collections_generic)
    make_dummy_generic(
        "Dictionary",
        ["TKey", "TValue"],
        ns_system_collections_generic,
    )

    make_dummy_class("AnimationPlayer", ns_godot)
    make_dummy_class("Area3D", ns_godot)
    make_dummy_class("Button", ns_godot)
    make_dummy_class("ButtonGroup", ns_godot)
    make_dummy_class("Color", ns_godot)
    make_dummy_class("ColorRect", ns_godot)
    make_dummy_class("Control", ns_godot)
    make_dummy_class("GpuParticles3D", ns_godot)
    make_dummy_class("HBoxContainer", ns_godot)
    make_dummy_class("Label", ns_godot)
    make_dummy_class("Marker3D", ns_godot)
    make_dummy_class("MeshInstance3D", ns_godot)
    make_dummy_class("NavigationAgent3D", ns_godot)
    make_dummy_class("Node", ns_godot)
    make_dummy_class("Node3D", ns_godot)
    make_dummy_class("PackedScene", ns_godot)
    make_dummy_class("ProgressBar", ns_godot)
    make_dummy_class("ShaderMaterial", ns_godot)
    make_dummy_class("StaticBody3D", ns_godot)
    make_dummy_class("Texture2D", ns_godot)
    make_dummy_class("Timer", ns_godot)
    make_dummy_class("VBoxContainer", ns_godot)
    make_dummy_class("Vector3", ns_godot)

    make_dummy_class("Regex", ns_system_text_regularexpressions)

    make_dummy_class("bool", codebase.global_namespace)
    make_dummy_class("float", codebase.global_namespace)
    make_dummy_class("int", codebase.global_namespace)
    make_dummy_class("string", codebase.global_namespace)


print("Parsing C# files...")
project_dir = "gdfire"
trees = parse_files(f"test_scripts/{project_dir}")
out_path = f"out/{project_dir}"

# Step 2: build code database of stuff in file
print("Gathering namespaces and types...")
codebase = Codebase()
populate_with_dummy(codebase)
gather_namespace_and_types(trees, codebase)
gather_class_elements(codebase)
consolidate_class_usings(codebase)

# Step 3: emit cpp code based on the code database
prepare_out_directory(out_path)
codebase.emit_cpp(out_path)

print("All done!")
