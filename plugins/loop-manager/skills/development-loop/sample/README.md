# Sample repo for the development loop

A tiny Node project (no packages to install, Node 18 or newer) with one real-feeling issue:
`slugify` makes unsafe, overlong web addresses from post titles. The tests for the fix are
already written and locked, so the loop's "done?" check (`make verify`) has something exact to
say.

## Try it

```sh
cp -R "$(dirname <this file>)" ~/devloop-sample && cd ~/devloop-sample
mv gitignore .gitignore
git init -q && git add . && git commit -qm "sample start"
make verify            # fails: the issue isn't fixed yet
claude
> /loop-manager:development-loop "$(cat ISSUE.md)"
```

The loop makes its working copy at `~/devloop-sample-devloop`, on a `devloop/<run>` branch. With
`"pr": false` in `devloop.json` it prints the branch at the end instead of opening a pull request.
`.devloop/<run>/` holds the goal, the log and the findings; `loop_report.py` turns them into numbers.

Files:

| File | Locked? | What it is |
|---|---|---|
| `ISSUE.md` | | The issue, as someone would file it |
| `src/slugify.js`, `bin/slugify.js` | | The code to fix |
| `test/slugify.test.js` | yes | What done means, including the command line |
| `Makefile` | yes | Defines `make verify`; locked so the check can't be loosened |
| `package.json` | yes | Locked for the same reason |
| `devloop.json` | always | The check and the locked list; a person writes it |
