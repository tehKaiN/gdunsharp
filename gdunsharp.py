from __future__ import annotations
import os
import glob
from enum import Enum
import tree_sitter_c_sharp
from tree_sitter import Language, Parser, Node, Tree

# TODO nested classes:
# ERR: type AiState not found
# ERR: type SummaryMode not found

# TODO collection types:
# ERR: type HashSet<ITeamMember> not found
# ERR: type List<TurretTower> not found
# ERR: type List<SpawnPoint> not found
# ERR: type List<ControlPoint> not found
# ERR: type List<Player> not found
# ERR: type List<Tank> not found
# ERR: type Dictionary<Player, PlayerStats> not found
# ERR: type HashSet<ITargetableTeamMember> not found


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
    GENERIC_NAME = "generic_name"
    ARRAY_TYPE = "array_type"


class CodeIdentifier:
    def __init__(self, name: str):
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
    def __init__(
        self, name: str, parent_namespace: CodeNamespace, is_dummy: bool = False
    ):
        super().__init__(name)
        self.parent_namespace = parent_namespace
        self.is_dummy = is_dummy
        parent_namespace.types[name] = self

    def get_forward_declaration(self) -> str:
        raise NotImplementedError("CodeType.get_forward_declaration()")

    def get_header_contents(self) -> str:
        raise NotImplementedError("CodeType.get_header_contents()")

    def emit_cpp(self, path: str):
        if not self.is_dummy:
            with open(f"{path}/{camel_to_snake(self.name)}.hpp", "w") as out_file:
                out_file.write(self.get_header_contents())


class DummyType(CodeType):
    def __init__(self, name, parent_namespace):
        super().__init__(name, parent_namespace, is_dummy=True)


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


class CodeClass(CodeType):
    def __init__(self, name: str, kind: CodeClassKind, parent_namespace: CodeNamespace):
        super().__init__(name, parent_namespace)
        self.kind = kind
        self.ancestors: list[CodeClass] = []
        self.properties: list[CodeProperty] = []
        self.fields: dict[str, CodeField] = {}
        self.methods: list[CodeMethod] = []
        self.usings: list[CodeNamespace] = []

        self.contexts: list[ClassNodeContext] = []

    def get_forward_declaration(self) -> str:
        return f"class {self.name};"

    def get_header_contents(self) -> str:
        out = "#pragma once\n\n"

        for using in self.usings:
            out += f"#include <{using.get_header_path()}>\n"
        out += "\n"

        ns_name = self.parent_namespace.get_full_path().replace(".", "::")
        out += f"namespace {ns_name} {{\n\n"

        for using in self.usings:
            out += f"using namespace {using.get_full_path().replace('.','::')};\n"
        out += "\n"

        out += f"class {self.name} {{\n"
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
        super().__init__(name, parent_namespace)
        self.entries: list[CodeEnumEntry] = []

    def get_forward_declaration(self) -> str:
        return f"enum class {self.name};"

    def get_header_contents(self) -> str:
        out = "#pragma once\n\n"
        ns_name = self.parent_namespace.get_full_path().replace(".", "::")
        out += f"namespace {ns_name} {{\n\n"
        out += f"enum class {self.name} {{\n"

        for entry in self.entries:
            value_str = f" = {entry.value}" if entry.value else ""
            out += f"\t{entry.name}{value_str},\n"

        out += f"}};\n\n"
        out += f"}} // namespace {ns_name}\n"
        return out


class CodeNamespace(CodeIdentifier):
    def __init__(self, name: str, parent: CodeNamespace | None):
        super().__init__(name)
        self.parent = parent
        self.subnamespaces: dict[str, CodeNamespace] = {}
        self.types: dict[str, CodeType] = {}

        if parent:
            parent.subnamespaces[name] = self

    def get_full_path(self) -> str:
        full_namespace = self.name
        parent = self.parent
        while parent and parent.name:
            full_namespace = f"{parent.name}.{full_namespace}"
            parent = parent.parent
        return full_namespace

    def get_header_path(self) -> str:
        full_path = camel_to_snake(self.name)
        parent = self.parent
        while parent and parent.name:
            full_path = f"{camel_to_snake(parent.name)}/{full_path}"
            parent = parent.parent

        return f"{full_path}/namespace.hpp"

    def get_all_types(self) -> list[CodeType]:
        types = []
        for type in self.types.values():
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

        for type in self.types.values():
            type.emit_cpp(f"{path}")

    def get_namespace_header(self) -> str:
        ns_name = self.get_full_path().replace(".", "::")
        out = "#pragma once\n\n"
        out += f"namespace {ns_name} {{\n\n"
        for type in self.types.values():
            if not type.is_dummy:
                out += f"{type.get_forward_declaration()}\n"
        out += f"\n}} // namespace {ns_name}\n"

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
        self, type_name: str, usings: list[str], parent_namespace: CodeNamespace
    ) -> CodeType | None:
        namespaces: list[CodeNamespace] = []

        # Use parent namespace and all of its direct parents
        ns: CodeNamespace | None = parent_namespace
        while ns and ns != self.global_namespace:
            namespaces.append(ns)
            ns = ns.parent

        # After that's exhausted, use specific namespaces from `using`s
        namespaces += [self.get_namespace(using) for using in usings]
        namespaces += [self.global_namespace]

        for namespace in namespaces:
            if type_name in namespace.types:
                return namespace.types[type_name]

        print(f"ERR: type {type_name} not found")
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


def get_or_create_class_from_node(
    node: Node, namespace: CodeNamespace, usings: list[str]
) -> CodeClass:
    match node.grammar_name:
        case NodeKind.CLASS_DECLARATION.value:
            kind = CodeClassKind.CLASS
        case NodeKind.IFACE_DECLARATION.value:
            kind = CodeClassKind.INTERFACE
        case NodeKind.STRUCT_DECLARATION.value:
            kind = CodeClassKind.STRUCT

    for child in node.named_children:
        if child.grammar_name == NodeKind.IDENTIFIER.value:
            assert child.text
            class_name = child.text.decode()
            break

    assert class_name
    if class_name not in namespace.types:
        code_class = CodeClass(class_name, kind, namespace)
        # print(
        #     f"Found {kind.name.lower()} {class_name} in namespace {namespace.get_full_path()}"
        # )
    else:
        found_type = namespace.types[class_name]
        assert isinstance(found_type, CodeClass)
        code_class = found_type

    declaration_list_node = find_node_by_grammar_name(
        node, NodeKind.DECLARATION_LIST.value
    )
    assert declaration_list_node
    code_class.contexts.append(
        ClassNodeContext(declaration_list_node, namespace, usings)
    )
    return code_class


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
    if enum_name not in namespace.types:
        code_enum = CodeEnum(enum_name, namespace)
        if declaration_list_node:
            parse_enum_declaration_list(code_enum, declaration_list_node)
        # print(f"Found enum {enum_name} in namespace {namespace.get_full_path()}")
    else:
        found_type = namespace.types[enum_name]
        assert isinstance(found_type, CodeEnum)
        code_enum = found_type
    return code_enum


def create_class_field(
    classlike: CodeClass, node: Node, context: ClassNodeContext
) -> CodeField:
    declaration_node = find_node_by_grammar_name(node, "variable_declaration")
    assert declaration_node
    type_node = declaration_node.named_children[0]
    declarator_node = declaration_node.named_children[1]

    assert type_node.grammar_name in [
        NodeKind.IDENTIFIER.value,
        NodeKind.PREDEFINED_TYPE.value,
        NodeKind.GENERIC_NAME.value,
        NodeKind.ARRAY_TYPE.value,
    ]
    assert declarator_node.grammar_name == "variable_declarator"

    name_node = declarator_node.named_children[0]
    assert name_node.grammar_name == NodeKind.IDENTIFIER.value

    assert type_node.text
    type_name = type_node.text.decode()
    field_type = codebase.resolve_type(
        type_name, context.using_strs, context.parent_namespace
    )
    if not field_type:
        # TODO: replace with error
        field_type = DummyType(type_name, context.parent_namespace)

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
            case NodeKind.CLASS_DECLARATION.value | NodeKind.IFACE_DECLARATION.value:
                get_or_create_class_from_node(child_node, namespace, usings)
            case NodeKind.ENUM_DECLARATION.value:
                get_or_create_enum_from_node(child_node, namespace)


def gather_namespace_and_types(trees_by_path: dict[str, Tree], codebase: Codebase):
    for path in trees_by_path:
        tree = trees_by_path[path]
        namespace = codebase.global_namespace
        traverse_tree_level(tree.root_node, codebase, namespace, [])


def gather_class_fields_and_usings(codebase: Codebase):
    classlikes = [t for t in codebase.get_all_types() if isinstance(t, CodeClass)]
    print(f"Got {len(classlikes)} class-likes")
    for classlike in classlikes:
        for context in classlike.contexts:
            for declaration_node in context.declaration_list_node.named_children:
                match declaration_node.grammar_name:
                    case NodeKind.FIELD_DECLARATION.value:
                        create_class_field(classlike, declaration_node, context)

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

    DummyType("AnimationPlayer", ns_godot)
    DummyType("Area3D", ns_godot)
    DummyType("Button", ns_godot)
    DummyType("ButtonGroup", ns_godot)
    DummyType("Color", ns_godot)
    DummyType("ColorRect", ns_godot)
    DummyType("Control", ns_godot)
    DummyType("GpuParticles3D", ns_godot)
    DummyType("HBoxContainer", ns_godot)
    DummyType("Label", ns_godot)
    DummyType("Marker3D", ns_godot)
    DummyType("MeshInstance3D", ns_godot)
    DummyType("NavigationAgent3D", ns_godot)
    DummyType("Node", ns_godot)
    DummyType("Node3D", ns_godot)
    DummyType("PackedScene", ns_godot)
    DummyType("ProgressBar", ns_godot)
    DummyType("ShaderMaterial", ns_godot)
    DummyType("StaticBody3D", ns_godot)
    DummyType("Texture2D", ns_godot)
    DummyType("Timer", ns_godot)
    DummyType("VBoxContainer", ns_godot)
    DummyType("Vector3", ns_godot)

    DummyType("Regex", ns_system_text_regularexpressions)

    DummyType("bool", codebase.global_namespace)
    DummyType("float", codebase.global_namespace)
    DummyType("int", codebase.global_namespace)
    DummyType("int[]", codebase.global_namespace)
    DummyType("string", codebase.global_namespace)


print("Parsing C# files...")
project_dir = "gdfire"
trees = parse_files(f"test_scripts/{project_dir}")
out_path = f"out/{project_dir}"

# Step 2: build code database of stuff in file
print("Gathering namespaces and types...")
codebase = Codebase()
populate_with_dummy(codebase)
gather_namespace_and_types(trees, codebase)
gather_class_fields_and_usings(codebase)

# Step 3: emit cpp code based on the code database
prepare_out_directory(out_path)
codebase.emit_cpp(out_path)

print("All done!")
