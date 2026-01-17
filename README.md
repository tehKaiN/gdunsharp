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
  - Access modifiers can be ignored and everything can be `public`
  - `readonly`, `sealed`, as well as class' `static` modifiers can be ignored
  - `out`/`ref` can be unified into single flavor of pass-by-reference
- Code should be human-readable, but doesn't need to be optimal:
  - Everything is emitted in .hpp files

The code translation works as follows:

1. Read files with tree-sitter
1. Translate tree-sitter's tree to code outline with additional context
1. Emit C++
1. ???
1. PROFIT

## Current state of the project

This project is far from complete. See [Roadmap](doc/roadmap.md).

## Note about license

The project is in its infancy and to ensure its development the software is licensed under Mozilla Public License 2.0.
This means that any changes to MPLed file must be made public (preferrably in Pull Request to this repo).

This **does not** mean that using this project relicenses your game code under MPL - it stays under whatever license you are using.
The only exception is copying part of MPL code to your project file - this file automatically would become MPLed.

Complying with license in your game is as simple as putting a notice similar to following in easily-accessible place accessible by a player, e.g. next to Godot license:

```
This game uses GdUnsharp - its source code is available on https://github.com/tehKaiN/GdUnsharp
```

If the project matures enough or gains opportunity to integrate with larger project, e.g. Godot itself, I might relicense it something more fitting and permissive like BSD or MIT.
By contributing a PR to this repo, you understand that and allow me to do so with your changes in the future.
