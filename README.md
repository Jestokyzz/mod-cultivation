# mod-cultivation

`mod-cultivation` is an AzerothCore 3.3.5a umbrella module for cultivation-style class subsystems.

The first subsystem is `rogue`, which contains the Celestial and Sha rogue variants. The public command surface is namespaced accordingly:

```text
.cultivation rogue celestial
.cultivation rogue sha
.cultivation rogue status
.cultivation rogue sync
.cultivation rogue reset
```

The former `.roguepath` command is removed. Existing character choices are preserved by the versioned `2.0.0` migration, which renames the persistent tables instead of recreating them.

This repository state is an unaccepted development candidate. It may be published to a candidate branch, but must not be tagged, released, or merged to `main` until isolated runtime tests and explicit user acceptance pass. See [README_RU.md](README_RU.md) for build, migration, validation, and rollback details.
