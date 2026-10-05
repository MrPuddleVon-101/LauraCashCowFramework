/** Brand assets live under the deploy's base path, which is the repository
 *  subpath on GitHub Pages and plain "/" everywhere else. Hard coding "/brand"
 *  sent every image to the domain root and broke the whole collage on Pages. */
export const asset = (path: string) =>
  `${import.meta.env.BASE_URL}${path.replace(/^\//, "")}`;
