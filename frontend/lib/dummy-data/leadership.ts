export interface LeadershipMessage {
  id: string;
  name: string;
  role: string;
  shortMessage: string;
  fullMessage: string;
  /** Tailwind gradient classes used as placeholder portrait background. */
  accent: string;
  initials: string;
  signature?: string;
  order: number;
}

export const LEADERSHIP: LeadershipMessage[] = [
  {
    id: "chairman",
    name: "Mr. A. Al Hassan",
    role: "Chairman",
    shortMessage:
      "Our purpose is to serve communities with quality products and trusted service across every business we operate.",
    fullMessage:
      "When we founded Paris United Group, we set out to build a company that families could rely on for the essentials of daily life. Today we operate across distribution, retail, and services with the same belief: that quality, service, and consistency win the long game. I am proud of every team member who turns up each day to keep that promise, and I am excited about what the next decade of growth will bring.",
    accent: "from-blue-600 via-indigo-600 to-purple-600",
    initials: "AH",
    signature: "Mr. A. Al Hassan",
    order: 1,
  },
  {
    id: "md",
    name: "Mr. K. Rahman",
    role: "Managing Director",
    shortMessage:
      "Operational excellence and customer obsession are how we turn strategy into measurable results.",
    fullMessage:
      "Running a diversified group means making thoughtful decisions every single day — about pricing, range, partnerships, technology, and people. Our task is to make sure each business is a great experience for customers and a great place to work. We invest in talent, in process, and in the systems that let our teams move faster than the market.",
    accent: "from-emerald-600 via-teal-600 to-cyan-600",
    initials: "KR",
    signature: "Mr. K. Rahman",
    order: 2,
  },
  {
    id: "ed-retail",
    name: "Ms. S. Khan",
    role: "Executive Director – Retail",
    shortMessage:
      "Retail is detail. Every shelf, every till, every interaction is a chance to delight.",
    fullMessage:
      "Across Paris Hyper Market, Paris Express, Al Mihrab, and Maharib Fish we serve hundreds of thousands of customers every week. We design our stores around the way people actually shop — fast, fresh, and welcoming. The next chapter is about deepening loyalty and bringing more digital convenience into the physical store experience.",
    accent: "from-rose-600 via-pink-600 to-fuchsia-600",
    initials: "SK",
    signature: "Ms. S. Khan",
    order: 3,
  },
  {
    id: "ed-distribution",
    name: "Mr. R. Iyer",
    role: "Executive Director – Distribution",
    shortMessage:
      "Reliable distribution is invisible when it works. We make it work for thousands of partners every day.",
    fullMessage:
      "Our distribution businesses move FMCG, fresh produce, packaging, and building materials across Qatar and the wider region. The work is logistical, technical, and relational — and we take every link seriously. From cold-chain investment to category management partnerships, we focus on dependable service that lets our customers grow.",
    accent: "from-amber-600 via-orange-600 to-red-600",
    initials: "RI",
    signature: "Mr. R. Iyer",
    order: 4,
  },
];

export function getLeadership(): LeadershipMessage[] {
  return [...LEADERSHIP].sort((a, b) => a.order - b.order);
}

export function getLeader(id: string): LeadershipMessage | undefined {
  return LEADERSHIP.find((l) => l.id === id);
}
