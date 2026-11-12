Post links break when a title has accents, symbols or is long

Our blog makes each post's address from its title with `slugify` (`src/slugify.js`). Today it
only lowercases and swaps spaces for dashes, so:

- "Café & Crème Brûlée" becomes `café-&-crème-brûlée`, which some browsers mangle;
- "Hello,   world!!" becomes `hello,---world!!`;
- a 120-character title makes a 120-character address.

Make slugs safe and short:

1. Lowercase, with accents taken off letters (é to e, ü to u, ß to ss).
2. `&` becomes the word `and`.
3. Anything that isn't a letter or digit becomes a dash, and several in a row become one.
   No dash at the start or end.
4. At most `max` characters (default 50). Cut at a dash, never in the middle of a word, unless
   the first word alone is longer than `max`; then cut that word at `max`.
5. A title with no letters or digits gives an empty string.

The command line tool `bin/slugify.js "<title>"` prints the slug, and takes `--max <n>`.
