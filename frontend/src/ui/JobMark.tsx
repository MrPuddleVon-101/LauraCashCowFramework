/* An emblem for each job.
 *
 * Seven jobs and one refusal, each drawn rather than labelled, in the same ink
 * as the rest of the page. They are SVG, so they are sharp at any size and
 * cost nothing to fetch, and they are drawn here rather than sourced because
 * stock art for "liability matcher" does not exist and a generic icon set
 * would say nothing about what the job is.
 *
 * Each mark is the job's actual mechanism, not a mood: the matcher is a key
 * meeting a dated lock, liquidity is a tap, defensive is ballast on a line.
 */

type Props = { name: string; size?: number; color?: string; className?: string };

/* A line that wobbles like a hand, from a seed, so no two marks share an
   identical stroke. */
function hand(points: [number, number][], seed = 7, amp = 0.9) {
  let s = seed;
  const rnd = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff - 0.5) * 2;
  return points
    .map(([x, y], i) => `${i ? "L" : "M"}${(x + rnd() * amp).toFixed(1)} ${(y + rnd() * amp).toFixed(1)}`)
    .join(" ");
}

const MARKS: Record<string, (c: string) => JSX.Element> = {
  // Core growth: a trunk with its rings. Broad, boring, held the whole way.
  CG: (c) => (
    <>
      <path d={hand([[32, 56], [32, 20]], 3)} stroke={c} strokeWidth="3.4" strokeLinecap="round" />
      <path d={hand([[32, 38], [18, 26]], 9)} stroke={c} strokeWidth="2.4" strokeLinecap="round" />
      <path d={hand([[32, 44], [46, 31]], 15)} stroke={c} strokeWidth="2.4" strokeLinecap="round" />
      <path d="M14 56q18 5 36 0" stroke={c} strokeWidth="2" fill="none" strokeLinecap="round" />
    </>
  ),

  // Satellite: one small researched bet, held in orbit, deliberately small.
  SG: (c) => (
    <>
      <circle cx="32" cy="38" r="9" stroke={c} strokeWidth="3" fill="none" />
      <ellipse cx="32" cy="38" rx="24" ry="11" stroke={c} strokeWidth="1.8" fill="none"
               transform="rotate(-22 32 38)" strokeDasharray="4 5" />
      <circle cx="53" cy="29" r="4" fill={c} />
    </>
  ),

  // International: a globe, with the meridian that is not America.
  ID: (c) => (
    <>
      <circle cx="32" cy="36" r="19" stroke={c} strokeWidth="3" fill="none" />
      <ellipse cx="32" cy="36" rx="8" ry="19" stroke={c} strokeWidth="1.9" fill="none" />
      <path d="M13 36h38" stroke={c} strokeWidth="1.9" strokeLinecap="round" />
      <path d="M17 25q15 7 30 0M17 47q15-7 30 0" stroke={c} strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </>
  ),

  // Liability matcher: a key cut for one dated lock. Certainty beats yield.
  LM: (c) => (
    <>
      <circle cx="20" cy="30" r="8" stroke={c} strokeWidth="3" fill="none" />
      <path d={hand([[27, 34], [50, 48]], 5)} stroke={c} strokeWidth="3" strokeLinecap="round" />
      <path d="M42 41l4 7M47 45l3 6" stroke={c} strokeWidth="2.6" strokeLinecap="round" />
      <path d="M12 54h40" stroke={c} strokeWidth="1.6" strokeDasharray="3 4" strokeLinecap="round" />
    </>
  ),

  // Liquidity: a tap you can open on any day. Short, boring on purpose.
  LR: (c) => (
    <>
      <path d="M16 24h22v9H16z" stroke={c} strokeWidth="2.6" fill="none" />
      <path d={hand([[38, 28], [48, 28], [48, 40]], 11)} stroke={c} strokeWidth="2.6" fill="none" strokeLinecap="round" />
      <path d="M24 18v6" stroke={c} strokeWidth="2.6" strokeLinecap="round" />
      <path d="M48 45c0 3-2 5-4 5s-4-2-4-5 4-7 4-7 4 4 4 7z" fill={c} />
    </>
  ),

  // Residual growth: the line that keeps going after the last payment.
  LG: (c) => (
    <>
      <path d="M12 50q12 2 18-8t20-20" stroke={c} strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M41 20h11v11" stroke={c} strokeWidth="2.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M30 56v-9" stroke={c} strokeWidth="1.8" strokeDasharray="3 4" strokeLinecap="round" />
    </>
  ),

  // Defensive: ballast, hung on the line, pulling the other way.
  DA: (c) => (
    <>
      <path d="M32 14v12" stroke={c} strokeWidth="2.4" strokeLinecap="round" />
      <path d="M18 26h28l-4 24H22z" stroke={c} strokeWidth="3" fill="none" strokeLinejoin="round" />
      <path d="M24 34h16" stroke={c} strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="32" cy="20" r="4" stroke={c} strokeWidth="2.2" fill="none" />
    </>
  ),

  // The refusal: a gate with nothing behind it.
  NO: (c) => (
    <>
      <path d="M14 20v34M50 20v34" stroke={c} strokeWidth="3" strokeLinecap="round" />
      <path d={hand([[18, 28], [46, 28]], 7)} stroke={c} strokeWidth="2.6" strokeLinecap="round" />
      <path d={hand([[18, 40], [46, 40]], 21)} stroke={c} strokeWidth="2.6" strokeLinecap="round" />
      <path d="M22 18l20 44" stroke={c} strokeWidth="3.4" strokeLinecap="round" />
    </>
  ),
};

export default function JobMark({ name, size = 64, color = "currentColor", className = "" }: Props) {
  const draw = MARKS[name];
  if (!draw) return null;
  return (
    <svg
      className={`jobmark ${className}`}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      fill="none"
      strokeLinecap="round"
      aria-hidden="true"
    >
      {draw(color)}
    </svg>
  );
}
