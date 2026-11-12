# Sample repo for the development loop

A tiny Node project (no packages to install, Node 18 or newer) with one real-feeling issue:
`slugify` makes unsafe, overlong web addresses from post titles. The tests for the fix are
already written and locked, so the loop's "done?" check (`make verify`) has something exact to
say.

## Try it

Copy the sample out of the repo and give it a first commit. It needs git, make and Node 18 or
newer, and nothing to install:

```sh
git clone https://github.com/omars-lab/claude-code-plugins
cp -R claude-code-plugins/plugins/loop-manager/skills/development-loop/sample devloop-sample
cd devloop-sample
mv gitignore .gitignore
git init -q && git add . && git commit -qm "sample start"
# fails 8 of its 10 tests: the issue isn't fixed yet
make verify
claude
```

Then, in Claude Code:

```text
/loop-manager:development-loop the issue in ISSUE.md
```

The loop works in its own copy next to the sample, at `devloop-sample-devloop`, and commits to a
`devloop/<run>` branch that the sample can see too. With `"pr": false` in `devloop.json` it prints
the branch at the end instead of opening a pull request. `.devloop/<run>/` holds the goal, the log
and the findings; `loop_report.py` turns them into numbers. To see the result:

```sh
git switch devloop/<run>
make verify     # all 10 pass
```

Files:

| File | Locked? | What it is |
|---|---|---|
| `ISSUE.md` | | The issue, as someone would file it |
| `src/slugify.js`, `bin/slugify.js` | | The code to fix |
| `test/slugify.test.js` | yes | What done means, including the command line |
| `Makefile` | yes | Defines `make verify`; locked so the check can't be loosened |
| `package.json` | yes | Locked for the same reason |
| `devloop.json` | always | The check and the locked list; a person writes it |
