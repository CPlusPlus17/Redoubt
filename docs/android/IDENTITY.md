# What this project is, and what it may call itself

Read this before touching anything that names the project, and before assuming
what we can publish or where.

## The correction that produced this file

Most of this board was planned on an unstated assumption: that this work was being
done **by** the LibreWolf project. It is not. This repository is a fork of
`librewolf.dev/librewolf/source`, worked on by someone who is not a LibreWolf
developer.

That assumption reached eleven tasks — "Set up the LibreWolf F-Droid repository",
"Publish the Android pages on librewolf.net", "Update the FAQ and close out issue
2169", the signing key, the Codeberg tracker. All of those have been re-scoped or
placeholdered. If you find another, it is a bug: fix it rather than working around it.

## The licence gives you the code, not the name

The source is **MPL-2.0**. Section 3.4 is explicit: the licence grants no rights in
any contributor's trademarks, service marks or logos.

So:

| | |
|---|---|
| fork the code, modify it, ship it | **yes** — that is what the MPL is for |
| ship it *called* "LibreWolf" | **no** |
| ship LibreWolf's privacy configuration | **yes**, with attribution |
| imply LibreWolf built, endorses or supports it | **no** |

There is an obvious precedent: LibreWolf exists in significant part *because*
Mozilla's trademark policy forbids shipping modified builds as "Firefox". Doing to
LibreWolf what Mozilla forbids being done to it would be a poor way to treat the
project whose work this depends on.

The practical objection matters more than the legal one. A user installing
"LibreWolf" from F-Droid would reasonably believe the LibreWolf team built it and
would judge its security posture on that basis. They would be wrong, and the
mistake would be ours.

## Placeholders in the board

These are greppable on purpose. When the name is chosen, it is one pass of `sed`.

    <PROJECT>          the product name shown to users
    <PROJECT_ID>       the Android applicationId, e.g. tld.example.browser
    <PROJECT_DOMAIN>   the site that hosts downloads and the parity statement
    <PROJECT_FORGE>    where the code and issues live

**`<PROJECT_ID>` is one-way.** A changed applicationId is a different app to
Android: no upgrade path, no data migration, every user reinstalls by hand. It is
the same severity as losing the signing key, and F-Droid and Accrescent both key on
it. Decide it before the first public build, not after.

Note the current build still ships as `org.mozilla` + `.fenix.debug`. That must
change before anything is published: it is Mozilla's namespace *and* it collides
with a real Firefox install.

## What stays "librewolf" and is not a naming question

The fork inherits upstream identifiers, and they are code, not branding. Leave them:

    settings/librewolf.cfg              the config file autoconfig reads
    scripts/librewolf-patches.py        the patcher
    librewolf.* prefs                   12 of them, compiled into StaticPrefList
    lw/ , librewolf-<version>-<release> build paths and the source dir name

Renaming these buys nothing, breaks every patch that references them, and would
make rebasing against upstream needlessly painful. `--with-app-name` and the
user-visible strings are the branding surface; those belong to LW-M4-07 and
LW-M4-12.

## What is unaffected

All of the engineering. The three-way patch split, the Android build, the
autoconfig channel, the telemetry removal, the measurements. None of it depends on
what the result is called.

## Attribution is not optional

The privacy configuration *is* the product. Roughly 267 pref decisions in
`settings/librewolf.cfg`, and the patch set that makes them enforceable, are
LibreWolf's work. LW-M7-03 owns saying so prominently rather than in a licence
footer. See also `docs/android/UPSTREAM-REPORTS.md` — three defects found in their
build that are worth reporting back whether or not anything else here goes anywhere.
