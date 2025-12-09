# Roadmap

Development is split across complexity levels.
Current level: **1**.

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
- emitting fields in interfaces
- emitting fields in classes
- emitting enums
- preventing emission of interface fields in classes

## Level 3

- reading fields with generic types
- reading fields with array types
- reading fields with dict types
- translating c# arrays to c++ vectors
- reading method signatures
- emitting dummy methods in .cpp files
- making sure stuff builds at all

## Level 4

- reading nested types in classes
- resolving nested types in classes
- emitting nested types
- reading signal signatures
- emitting signal code

## Uncategorized

- reading properties
- reading method bodies
- `async`/`await`
- somehow support Newtonsoft.JSON
- build as engine module
- `using Foo = Bar`
- reading scoped namespaces
- build as GDExtension
