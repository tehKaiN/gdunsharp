# Roadmap

Development is split across complexity levels.
Current level: **4**.

## Level 1

- construct namespace hierarchy
- read interface signatures
- read class signatures
- read enum signatures
- read field signatures
- support for basic godot/builtin types

## Level 2

- emit empty interfaces in .hpp files
- emit empty classes in .hpp files
- emit fields in classes
- emit enums
- add namespace includes in .hpp files
- add subincludes in namespace includes

## Level 3

- read fields with generic types
- read fields with array types
- read fields with dict types
- add parse error on tuples
- read method signatures
- read generic method signatures
- emit method signatures in class definitions
- emit dummy method bodies

## Level 4

- read properties
- emit properties for classes
- emit virtual methods for interfaces
- parse inheritance chain
- emit inheritance chain
- preserve virtual/override in methods
- emit virtual property accessors for interfaces
- emit `override` for methods/accessors that implement interface
- translate c# collections to godot equivalents

## Level 5

- replace remaining c# system types with external types from godot-cpp
- make sure stuff builds at all
- read signal signatures
- emit signal boilerplate

## Level 6 - usable

- read method bodies
- emit method bodies
- read static methods
- resolve extension methods
- resolve generic parameters in class
- resolve generic parameters in methods
- build as engine module
- build as GDExtension

## Future

- read nested types in classes
- resolve nested types in classes
- emit nested types
- `using Foo = Bar`
- `async`/`await`
- somehow support Newtonsoft.JSON
- read scoped namespaces
