/**
 * Mirror of backend Pydantic schemas — Digital Offers & Catalogue
 * module (app/schemas/marketing.py).
 */

export type CatalogueProcessingStatus =
  | "pending"
  | "processing"
  | "ready"
  | "failed";

// ---------------------------------------------------------------------------
// Campaigns
// ---------------------------------------------------------------------------

export interface OfferCampaign {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  banner_image_url: string | null;
  theme_color: string | null;
  branch: string | null;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
  is_featured: boolean;
  is_killer_offer: boolean;
  is_flash_sale: boolean;
  sort_order: number;
  meta_title: string | null;
  meta_description: string | null;
  view_count: number;
  catalogue_count: number;
  created_at: string;
  updated_at: string;
}

export interface OfferCampaignCreate {
  slug: string;
  title: string;
  description?: string | null;
  banner_image_url?: string | null;
  theme_color?: string | null;
  branch?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  is_active?: boolean;
  is_featured?: boolean;
  is_killer_offer?: boolean;
  is_flash_sale?: boolean;
  sort_order?: number;
  meta_title?: string | null;
  meta_description?: string | null;
}

export type OfferCampaignUpdate = Partial<OfferCampaignCreate>;


// ---------------------------------------------------------------------------
// Catalogues
// ---------------------------------------------------------------------------

export interface CataloguePage {
  page_number: number;
  image_url: string;
  thumbnail_url: string;
  width: number;
  height: number;
}

export interface Catalogue {
  id: number;
  campaign_id: number | null;
  slug: string;
  title: string;
  description: string | null;
  cover_image_url: string | null;
  qr_logo_url: string | null;
  pdf_url: string | null;
  page_count: number;
  processing_status: CatalogueProcessingStatus;
  processing_error: string | null;
  is_active: boolean;
  is_featured: boolean;
  sort_order: number;
  view_count: number;
  download_count: number;
  file_size_bytes: number | null;
  meta_title: string | null;
  meta_description: string | null;
  created_at: string;
  updated_at: string;
}

export interface CatalogueDetail extends Catalogue {
  pages: CataloguePage[];
}

export interface CatalogueUpdate {
  slug?: string;
  title?: string;
  description?: string | null;
  campaign_id?: number | null;
  is_active?: boolean;
  is_featured?: boolean;
  sort_order?: number;
  meta_title?: string | null;
  meta_description?: string | null;
}

export interface CatalogueAnalytics {
  catalogue_id: number;
  total_views: number;
  unique_sessions: number;
  by_device: Record<string, number>;
  last_7_days: Array<{ date: string; views: number }>;
}
