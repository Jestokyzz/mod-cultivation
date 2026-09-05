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

Version **v2.0.0** was accepted by the user and installed on the production JestokyCraft server/client on 2026-09-05. Download the complete compatible Windows package from GitHub Releases, not the source-code ZIP. See [installation](docs/install-v2.0.0.md), [release notes](CHANGELOG_RU.md), and [acceptance scope](docs/audit-fixes-20260905.md). The prebuilt binary is for the documented JestokyCraft integration, not arbitrary AzerothCore installations. Unverified edge cases remain explicitly listed.
