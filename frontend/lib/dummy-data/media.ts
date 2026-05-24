export type MediaCategory = "stores" | "events" | "team" | "campaigns";
export type MediaKind = "image" | "video";

export interface MediaItem {
  id: string;
  title: string;
  description: string;
  kind: MediaKind;
  category: MediaCategory;
  /** Tailwind gradient classes used as the placeholder tile. */
  accent: string;
  /** Tile aspect ratio class (Tailwind aspect-*). */
  aspect: string;
}

export const MEDIA: MediaItem[] = [
  { id: "m1", title: "Lusail hypermarket opening", description: "Day-one crowd at the new flagship.", kind: "image", category: "events", accent: "from-rose-500 via-red-500 to-orange-400", aspect: "aspect-[4/3]" },
  { id: "m2", title: "Cold-chain fleet", description: "Refrigerated trucks at the central DC.", kind: "image", category: "stores", accent: "from-emerald-500 via-teal-500 to-cyan-400", aspect: "aspect-[3/4]" },
  { id: "m3", title: "Back to School 2026", description: "5,000 kits distributed.", kind: "image", category: "campaigns", accent: "from-fuchsia-500 via-pink-500 to-rose-400", aspect: "aspect-square" },
  { id: "m4", title: "Service centre walkthrough", description: "YellowTech Garage tour.", kind: "video", category: "team", accent: "from-amber-500 via-yellow-500 to-orange-400", aspect: "aspect-video" },
  { id: "m5", title: "Annual leadership summit", description: "Executives across divisions.", kind: "image", category: "events", accent: "from-indigo-500 via-blue-500 to-sky-400", aspect: "aspect-[4/3]" },
  { id: "m6", title: "Paris Express opening", description: "New minimart welcomes the neighbourhood.", kind: "image", category: "stores", accent: "from-violet-500 via-purple-500 to-fuchsia-400", aspect: "aspect-square" },
  { id: "m7", title: "Greentech property tour", description: "Featured listings.", kind: "video", category: "campaigns", accent: "from-teal-500 via-cyan-500 to-sky-400", aspect: "aspect-video" },
  { id: "m8", title: "Maharib Fresh team", description: "Sorting and packing shift.", kind: "image", category: "team", accent: "from-emerald-500 via-green-500 to-lime-400", aspect: "aspect-[3/4]" },
  { id: "m9", title: "Core Engineering site", description: "Fit-out in progress.", kind: "image", category: "stores", accent: "from-stone-500 via-amber-700 to-orange-600", aspect: "aspect-[4/3]" },
  { id: "m10", title: "Customer service Friday", description: "Behind the counter at Paris Hyper.", kind: "image", category: "team", accent: "from-blue-500 via-sky-500 to-cyan-400", aspect: "aspect-square" },
  { id: "m11", title: "EV bay launch", description: "Inside the new EV service area.", kind: "video", category: "events", accent: "from-amber-400 via-yellow-500 to-orange-500", aspect: "aspect-video" },
  { id: "m12", title: "Doha Fashion floor", description: "Cosmetics merchandising at retail floor.", kind: "image", category: "campaigns", accent: "from-rose-400 via-pink-500 to-fuchsia-500", aspect: "aspect-[4/3]" },
];

export function getMedia(): MediaItem[] {
  return MEDIA;
}

export const MEDIA_CATEGORY_LABELS: Record<MediaCategory, string> = {
  stores: "Stores",
  events: "Events",
  team: "Team",
  campaigns: "Campaigns",
};
