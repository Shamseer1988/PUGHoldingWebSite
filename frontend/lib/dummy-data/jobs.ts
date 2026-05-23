export type EmploymentType = "full_time" | "part_time" | "contract";
export type JobStatus = "open" | "on_hold" | "closed";

export interface JobOpening {
  slug: string;
  title: string;
  department: string;
  company: string;
  location: string;
  employmentType: EmploymentType;
  minExperience: number;
  maxExperience: number;
  education?: string;
  requiredSkills: string[];
  preferredSkills?: string[];
  description: string;
  responsibilities: string[];
  requirements: string[];
  status: JobStatus;
  postedAt: string;
}

export const JOBS: JobOpening[] = [
  {
    slug: "store-manager-paris-hyper-lusail",
    title: "Store Manager",
    department: "Retail Operations",
    company: "Paris Hyper Market",
    location: "Lusail, Qatar",
    employmentType: "full_time",
    minExperience: 6,
    maxExperience: 10,
    education: "Bachelor's degree (business / retail preferred)",
    requiredSkills: ["Retail operations", "Team management", "P&L", "Inventory"],
    preferredSkills: ["Hypermarket experience", "Arabic language"],
    description:
      "Lead the day-to-day operations of a new flagship hypermarket. You will own customer experience, sales performance, P&L, inventory accuracy, and a team of 80+.",
    responsibilities: [
      "Own daily store operations and KPIs",
      "Lead, coach, and develop department managers",
      "Drive sales, margin, and customer satisfaction",
      "Manage inventory, shrinkage, and supplier relationships",
      "Ensure compliance with health & safety and brand standards",
    ],
    requirements: [
      "6+ years in retail with at least 2 years as Store Manager",
      "Strong P&L, planning, and people leadership skills",
      "GCC retail experience preferred",
    ],
    status: "open",
    postedAt: "2026-05-10",
  },
  {
    slug: "fmcg-sales-executive",
    title: "FMCG Sales Executive",
    department: "Sales",
    company: "Paris Food International",
    location: "Doha, Qatar",
    employmentType: "full_time",
    minExperience: 2,
    maxExperience: 5,
    education: "Bachelor's degree",
    requiredSkills: ["FMCG sales", "Key accounts", "Negotiation", "Reporting"],
    description:
      "Develop and grow assigned FMCG accounts across department stores and HORECA. Manage promotions, in-store activations, and weekly sell-out reporting.",
    responsibilities: [
      "Manage assigned key accounts",
      "Negotiate annual contracts and promotions",
      "Drive in-store activations and brand visibility",
      "Maintain accurate weekly sell-out reporting",
    ],
    requirements: [
      "2-5 years FMCG field sales experience",
      "GCC market exposure preferred",
      "Valid Qatar driving licence is a plus",
    ],
    status: "open",
    postedAt: "2026-05-05",
  },
  {
    slug: "warehouse-supervisor",
    title: "Warehouse Supervisor",
    department: "Supply Chain",
    company: "Paris Food International",
    location: "Industrial Area, Doha",
    employmentType: "full_time",
    minExperience: 3,
    maxExperience: 7,
    requiredSkills: ["Warehouse ops", "WMS", "Cold chain", "Team supervision"],
    description:
      "Supervise a temperature-controlled distribution warehouse, ensuring SLAs for inbound, putaway, picking, and outbound operations.",
    responsibilities: [
      "Supervise warehouse shifts and operations",
      "Maintain WMS data accuracy and stock counts",
      "Coordinate inbound and outbound fleets",
      "Enforce safety and food handling standards",
    ],
    requirements: [
      "3+ years warehouse / DC supervision experience",
      "WMS familiarity (SAP / Oracle / equivalent)",
      "Cold-chain experience preferred",
    ],
    status: "open",
    postedAt: "2026-04-30",
  },
  {
    slug: "ev-technician",
    title: "EV Technician",
    department: "Vehicle Service",
    company: "YellowTech Garage",
    location: "Doha, Qatar",
    employmentType: "full_time",
    minExperience: 3,
    maxExperience: 8,
    requiredSkills: ["EV diagnostics", "High-voltage safety", "OEM tools"],
    preferredSkills: ["BEV certification", "Multi-brand experience"],
    description:
      "Service and repair electric vehicles in our newly opened EV bays. OEM certification training will be provided.",
    responsibilities: [
      "Diagnose and repair EV systems",
      "Follow high-voltage safety protocols",
      "Document service jobs and update WIP",
      "Mentor junior technicians",
    ],
    requirements: [
      "3+ years vehicle technician experience",
      "Existing EV or hybrid experience preferred",
      "Strong attention to safety",
    ],
    status: "open",
    postedAt: "2026-04-22",
  },
  {
    slug: "real-estate-broker",
    title: "Senior Real Estate Broker",
    department: "Real Estate",
    company: "Greentech Real Estate Broker",
    location: "Doha, Qatar",
    employmentType: "full_time",
    minExperience: 4,
    maxExperience: 9,
    requiredSkills: ["Sales", "Negotiation", "Qatar market", "CRM"],
    description:
      "Advise clients on residential and commercial property in Qatar. Build a strong pipeline of buyers, sellers, and tenants through proactive outreach and referrals.",
    responsibilities: [
      "Source and qualify leads",
      "Conduct viewings and negotiate offers",
      "Maintain CRM hygiene and pipeline reporting",
      "Build long-term client relationships",
    ],
    requirements: [
      "4+ years brokerage experience",
      "Strong Qatar market knowledge",
      "Valid driving licence",
    ],
    status: "open",
    postedAt: "2026-04-18",
  },
  {
    slug: "civil-engineer",
    title: "Civil Engineer",
    department: "Engineering",
    company: "Core Engineering and Construction",
    location: "Doha, Qatar",
    employmentType: "full_time",
    minExperience: 5,
    maxExperience: 12,
    education: "B.Sc. Civil Engineering",
    requiredSkills: ["Project management", "BOQ", "MEP coordination"],
    description:
      "Lead site execution for commercial fit-out projects. Coordinate MEP subcontractors, supervise quality, and report progress against schedule.",
    responsibilities: [
      "Lead project execution on site",
      "Coordinate subcontractors and consultants",
      "Track progress, quality, and safety",
      "Prepare BOQs and progress reports",
    ],
    requirements: [
      "B.Sc. Civil Engineering",
      "5+ years project execution experience",
      "GCC fit-out experience preferred",
    ],
    status: "open",
    postedAt: "2026-04-12",
  },
  {
    slug: "cashier-paris-express",
    title: "Cashier",
    department: "Retail Operations",
    company: "Paris Express",
    location: "Doha, Qatar",
    employmentType: "full_time",
    minExperience: 1,
    maxExperience: 3,
    requiredSkills: ["POS", "Customer service", "Cash handling"],
    description:
      "Provide fast, friendly service at the till and maintain accurate cash handling.",
    responsibilities: [
      "Operate POS and process transactions",
      "Provide warm customer service",
      "Maintain till accuracy and shift reports",
    ],
    requirements: [
      "1-3 years cashier experience",
      "Good spoken English; Arabic is a plus",
    ],
    status: "open",
    postedAt: "2026-04-05",
  },
  {
    slug: "hr-business-partner",
    title: "HR Business Partner",
    department: "Human Resources",
    company: "Paris United Group Holding",
    location: "Doha, Qatar",
    employmentType: "full_time",
    minExperience: 5,
    maxExperience: 10,
    requiredSkills: ["HRBP", "Employee relations", "Performance management"],
    description:
      "Partner with division leaders across retail and distribution to drive workforce planning, employee engagement, and talent development.",
    responsibilities: [
      "Act as trusted HR partner to senior leaders",
      "Lead workforce planning and engagement",
      "Coach managers on performance and development",
    ],
    requirements: [
      "5+ years HRBP experience in retail or FMCG",
      "Strong stakeholder management skills",
    ],
    status: "open",
    postedAt: "2026-03-28",
  },
];

export function getJobs(): JobOpening[] {
  return JOBS.filter((j) => j.status === "open");
}

export function getJobBySlug(slug: string): JobOpening | undefined {
  return JOBS.find((j) => j.slug === slug);
}

export function getDepartments(): string[] {
  return Array.from(new Set(JOBS.map((j) => j.department))).sort();
}

export function getJobCompanies(): string[] {
  return Array.from(new Set(JOBS.map((j) => j.company))).sort();
}

export function getJobLocations(): string[] {
  return Array.from(new Set(JOBS.map((j) => j.location))).sort();
}

export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
};
