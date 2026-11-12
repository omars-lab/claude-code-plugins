// Turns a post title into the last part of its web address.
export function slugify(title, { max = 50 } = {}) {
  return String(title).toLowerCase().replace(/ /g, "-");
}
