from __future__ import annotations
import glob
from enum import Enum
import tree_sitter_c_sharp
from tree_sitter import Language, Parser, Node, Tree


class NodeKind(Enum):
    CLASS_DECLARATION = "class_declaration"
    IFACE_DECLARATION = "interface_declaration"
    STRUCT_DECLARATION = "struct_declaration"
    ENUM_DECLARATION = "enum_declaration"
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
    def __init__(self, name: str):
        super().__init__(name)


class ClassNodeContext:
    def __init__(
        self,
        declaration_list_node: Node,
        parent_namespace: CodeNamespace,
        usings: list[str],
    ):
        self.declaration_list_node = declaration_list_node
        self.parent_namespace = parent_namespace
        self.usings = usings


class CodeClass(CodeType):
    def __init__(self, name: str, kind: CodeClassKind):
        super().__init__(name)
        self.kind = kind
        self.ancestors: list[CodeClass] = []
        self.properties: list[CodeProperty] = []
        self.fields: dict[str, CodeField] = {}
        self.methods: list[CodeMethod] = []

        self.contexts: list[ClassNodeContext] = []


class CodeEnumValue(CodeIdentifier):
    def __init__(self, name: str, value: str | None):
        super().__init__(name)
        self.value = value if value else ""


class CodeEnum(CodeType):
    def __init__(self, name: str):
        super().__init__(name)
        self.values: list[CodeEnumValue] = []


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

    def get_all_types(self) -> list[CodeType]:
        types = []
        for type in self.types.values():
            types.append(type)
        for child_name in self.subnamespaces:
            types += self.subnamespaces[child_name].get_all_types()
        return types


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
        ns: CodeNamespace | None = parent_namespace
        while ns and ns != self.global_namespace:
            namespaces.append(ns)
            ns = ns.parent
        namespaces += [self.get_namespace(using) for using in usings]
        namespaces += [self.global_namespace]

        for namespace in namespaces:
            if type_name in namespace.types:
                return namespace.types[type_name]

        print(f"ERR: type {type_name} not found")
        return None


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
        code_class = CodeClass(class_name, kind)
        namespace.types[class_name] = code_class
        print(
            f"Found {kind.name.lower()} {class_name} in namespace {namespace.get_full_path()}"
        )
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


def get_or_create_enum_from_node(node: Node, namespace: CodeNamespace) -> CodeEnum:
    for child in node.named_children:
        if child.grammar_name == NodeKind.IDENTIFIER.value:
            assert child.text
            enum_name = child.text.decode()
            break

    assert enum_name
    if enum_name not in namespace.types:
        code_enum = CodeEnum(enum_name)
        namespace.types[enum_name] = code_enum
        print(f"Found enum {enum_name} in namespace {namespace.get_full_path()}")
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
        type_name, context.usings, context.parent_namespace
    )
    if not field_type:
        field_type = CodeType(type_name)

    assert name_node.text
    field_name = name_node.text.decode()
    field = CodeField(field_name, field_type)
    classlike.fields[field.name] = field
    print(f"Added field {classlike.name}.{field.name} of type {field_type.name}")
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


def gather_class_fields(codebase: Codebase):
    classlikes = [t for t in codebase.get_all_types() if isinstance(t, CodeClass)]
    print(f"Got {len(classlikes)} class-likes")
    for classlike in classlikes:
        for node_context in classlike.contexts:
            for declaration_node in node_context.declaration_list_node.named_children:
                match declaration_node.grammar_name:
                    case NodeKind.FIELD_DECLARATION.value:
                        create_class_field(classlike, declaration_node, node_context)


print("Parsing C# files...")
trees = parse_files("test_scripts/gdfire")

print("Gathering namespaces and types...")
codebase = Codebase()
ns_system = CodeNamespace("System", codebase.global_namespace)
ns_system_linq = CodeNamespace("Linq", ns_system)
ns_system_collections = CodeNamespace("Collections", ns_system)
ns_system_collections_generic = CodeNamespace("Generic", ns_system_collections)
ns_system_io = CodeNamespace("IO", ns_system)
ns_system_text = CodeNamespace("Text", ns_system)
ns_system_text_regularexpressions = CodeNamespace("RegularExpressions", ns_system_text)
ns_godot = CodeNamespace("Godot", codebase.global_namespace)
ns_gdunit4 = CodeNamespace("GdUnit4", codebase.global_namespace)
ns_gdunit4_assertions = CodeNamespace("Assertions", ns_gdunit4)

ns_godot.types["AnimationPlayer"] = CodeType("AnimationPlayer")
ns_godot.types["Area3D"] = CodeType("Area3D")
ns_godot.types["Button"] = CodeType("Button")
ns_godot.types["ButtonGroup"] = CodeType("ButtonGroup")
ns_godot.types["Color"] = CodeType("Color")
ns_godot.types["ColorRect"] = CodeType("ColorRect")
ns_godot.types["Control"] = CodeType("Control")
ns_godot.types["GpuParticles3D"] = CodeType("GpuParticles3D")
ns_godot.types["HBoxContainer"] = CodeType("HBoxContainer")
ns_godot.types["Label"] = CodeType("Label")
ns_godot.types["Marker3D"] = CodeType("Marker3D")
ns_godot.types["MeshInstance3D"] = CodeType("MeshInstance3D")
ns_godot.types["NavigationAgent3D"] = CodeType("NavigationAgent3D")
ns_godot.types["Node"] = CodeType("Node")
ns_godot.types["Node3D"] = CodeType("Node3D")
ns_godot.types["PackedScene"] = CodeType("PackedScene")
ns_godot.types["ProgressBar"] = CodeType("ProgressBar")
ns_godot.types["ShaderMaterial"] = CodeType("ShaderMaterial")
ns_godot.types["StaticBody3D"] = CodeType("StaticBody3D")
ns_godot.types["Texture2D"] = CodeType("Texture2D")
ns_godot.types["Timer"] = CodeType("Timer")
ns_godot.types["VBoxContainer"] = CodeType("VBoxContainer")
ns_godot.types["Vector3"] = CodeType("Vector3")

ns_system_text_regularexpressions.types["Regex"] = CodeType("Regex")

codebase.global_namespace.types["bool"] = CodeType("bool")
codebase.global_namespace.types["float"] = CodeType("float")
codebase.global_namespace.types["int"] = CodeType("int")
codebase.global_namespace.types["int[]"] = CodeType("int[]")
codebase.global_namespace.types["string"] = CodeType("string")

gather_namespace_and_types(trees, codebase)
gather_class_fields(codebase)

# Step 2: build code database of stuff in file
# Step 3: emit cpp code based on the code database
print("All done!")
