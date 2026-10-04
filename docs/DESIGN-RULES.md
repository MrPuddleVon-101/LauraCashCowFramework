# Stonky x Cash Cows, Design Rules

Two lists. The first is everything we found that makes a site read as machine-assembled.
None of it is allowed in this codebase. The second is what we do instead.

## Banned

**Type**
- Inter, Poppins, Montserrat, Space Grotesk, Playfair Display, Roboto, `system-ui` as a brand face.
- One typeface doing every job, from the 64px headline to the footer small print.
- Headlines set in a gradient fill.
- Letter-spacing applied to lowercase body text.

**Colour**
- Violet to indigo gradients (`#7c3aed → #6366f1` and relatives). Tailwind `indigo-500` in any form.
- Decorative gradient blobs or mesh backgrounds behind a hero.
- Colour used with no semantic job. Every hue here means something or it does not ship.
- Glassmorphism panels stacked over a blurred photograph.
- A page that runs one shade from top to bottom and calls it a palette.

**Layout and components**
- One border radius on everything. One padding value on everything.
- Three equal feature cards in a row, each with a line icon above a two-word heading.
- Equal-height card grids where nothing is more important than anything else.
- A hero that occupies the full viewport and says nothing specific.
- Emoji used as interface icons.
- Centre-aligned everything.
- A paragraph where a picture would carry the same point faster.

**Motion**
- `fadeInUp` applied uniformly to every section on scroll.
- A custom cursor that hides the real one. It costs usability and buys nothing.
- Hover states that change nothing, or buttons that snap with no easing.
- Animation that does not communicate a state change.
- Scroll hijacking. The page scrolls at the speed the reader chose.

**Copy**
- Em dashes. Use a colon, a full stop, or a comma.
- "Seamless", "cutting-edge", "best-in-class", "unlock", "elevate", "harness the power of".
- "Build the future of X". "Your all-in-one platform."
- Hedges: "may help you", "can potentially".
- Any sentence that would survive unchanged on a different product's site.

## Instead

**Material.** The logo is an ink and gouache drawing on cream, so the interface is made of
the same things. Paper is the page. Ink is the type, and it runs past 14:1 against the
paper. Cards are pieces of paper laid down at a human angle with a hard, short cast
shadow and a strip of tape, never a 1px box with a blur behind it. Rules and circles and
arrows are drawn by a seeded wobble generator in `src/lib/draw.ts`, so a mark looks the
same on every render and nothing twitches when React re-runs a component.

**Type.** Fraunces for display, on its optical size, SOFT and WONK axes, because the logo
is hand drawn and the headline type should answer it. Archivo for interface text, a
grotesque with real working-copy character. IBM Plex Mono for tickers, scores, dates and
anything in a column of figures, always with tabular lining numerals so digits do not
shimmer while a value counts up.

**Colour.** Lifted straight off the logo. Gold is the client, and it is the only thing
Laura's name and the client's own figures are allowed to wear. Green, amber and red belong
exclusively to the signal ladder, so a green mark anywhere on this site means one thing:
the candidate cleared the Red Gate and both scores. Rose carries the liability calendar.
Sage carries the portfolio. The categorical ramp in `INKS` is for identity only, never for
magnitude.

**Rhythm.** The page is built from bands of flat colour: cream, ink, rose, gold. They meet
on a torn edge, not a rule, and the temperature changes as you move down. That is what
stops a long page reading as one undifferentiated surface.

**Motion.** One scroll clock in `src/lib/motion.ts` drives everything, and one
IntersectionObserver at the root marks entrances, so no component attaches its own
listener. Entrances are not uniform: a stamp lands, a cutout slides in from the margin, a
rule draws itself, a figure counts up once and then holds. The pipeline on the overview is
scrubbed by the scroll, because the order of the four steps is the whole argument and
making the reader move the candidate through it is better than telling them. The ticker
strip takes its speed from scroll velocity. The cow follows the pointer. Everything else
holds still.

**Visual before verbal.** A score is a stamp. A pair of scores is a pair of bars sized to
the exponent each carries. A model is a polar area chart whose wedge widths are its own
weights. Ten payments are ten columns. Look-through exposure is a treemap. Ten thousand
simulated outcomes are a range of hills. The prose that used to carry those points is cut
or folded away, and the audit trail lives behind one disclosure so the committee can still
get at all of it.

**Evidence.** Every figure on screen carries its source, its as-of date and its confidence.
Where a number could not be verified, the interface says so rather than rendering a
convincing placeholder. This is a rule from the PRD and it is also the fastest way to not
look generated.
