# Roadmap

Development is split across complexity levels.
Current level: **3**.

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
- preserve virtual/override in methods
- emit virtual property accessors for interfaces
- translate c# arrays to c++ vectors
- make sure stuff builds at all

## Level 5

- read nested types in classes
- resolve nested types in classes
- emit nested types
- read signal signatures
- emit signal code

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

- `us Foo = Bar`
- `async`/`await`
- somehow support Newtonsoft.JSON
- read scoped namespaces
