# Roadmap

Development is split across complexity levels.
Current level: **2**.

## Level 1

- constructing namespace hierarchy
- reading interface signatures
- reading class signatures
- reading enum signatures
- reading field signatures
- support for basic godot/builtin types

## Level 2

- emitting empty interfaces in .hpp files
- emitting empty classes in .hpp files
- emitting fields in classes
- emitting enums
- add namespace includes in .hpp files
- add subincludes in namespace includes

## Level 3

- reading fields with generic types
- reading fields with array types
- reading fields with dict types
- add parse error on tuples
- reading method signatures
- reading generic method signatures
- emitting method signatures in classes
- emitting dummy method bodies in .cpp files

## Level 4

- reading properties
- emitting properties for classes
- emitting virtual methods for interfaces
- preserving virtual/override in methods
- emitting virtual properties for interfaces
- translating c# arrays to c++ vectors
- making sure stuff builds at all

## Level 5

- reading nested types in classes
- resolving nested types in classes
- emitting nested types
- reading method bodies
- reading signal signatures
- emitting signal code

## Level 6 - usable

- emitting method bodies
- build as engine module
- build as GDExtension

## Future

- `using Foo = Bar`
- `async`/`await`
- somehow support Newtonsoft.JSON
- reading scoped namespaces
