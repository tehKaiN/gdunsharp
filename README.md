# GdUnsharp

A Godot-specific C# to C++ translation script.

This project doesn't try to be complete C# solution and just limits its scope to scripts written specifically in GodotSharp framework, which should translate to godot-dependent C++ in a straightforward manner.

## Usage

TODO

## How it works

The project exploits following assumptions:

- No third-party dependencies in C# code
- Code doesn't do anything fancy and is mostly just a glue logic:
  - Dotnet's `System` library is used sparingly and can be translated to stdlib/godot types
  - Lambdas are simple and are used sparingly
  - Runtime reflection isn't used
  - No pure C# events, just Godot signals
- C# code compiles, thus:
  - access modifiers can be ignored and everything can be `public`
  - `readonly` modified can be ignored
  - `out`/`ref` can be unified into single flavor of pass-by-reference

The code translation works as follows:

1. Read files with tree-sitter
1. Translate tree-sitter's tree to code outline with additional context
1. Emit C++
1. ???
1. PROFIT

## TODO

Development is split across complexity levels.
Current level: 1.

### Level 1

- constructing namespace hierarchy
- reading interface signatures
- reading class signatures
- reading enum signatures
- reading field signatures
- support for basic godot/builtin types

### Level 2

- emitting empty interfaces in .hpp files
- emitting empty classes in .hpp files
- emitting fields in interfaces
- emitting fields in classes
- emitting enums
- preventing emission of interface fields in classes

### Level 3

- reading fields with generic types
- reading fields with array types
- reading fields with dict types
- translating c# arrays to c++ vectors
- reading method signatures
- emitting dummy methods in .cpp files
- making sure stuff builds at all

### Level 4

- reading nested types in classes
- resolving nested types in classes
- emitting nested types
- reading signal signatures
- emitting signal code

### Uncategorized

- reading properties
- reading method bodies
- `async`/`await`
- somehow support Newtonsoft.JSON
- build as engine module
- `using Foo = Bar`
- reading scoped namespaces
- build as GDExtension
