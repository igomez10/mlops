/** Mirrors FastAPI `ListingResponse` / embedded listing JSON. */
export type Listing = {
  id: string
  marketplace_url: string
  image_url: string
  created_at: string
  status: string
  description: string
}

export type PriceEstimate = {
  low: number
  high: number
  currency: string
  reasoning: string
  comparable_sources: string[]
}

export type ProductAnalysis = {
  product_name: string
  brand: string
  model: string
  category: string
  condition_estimate: string
  visible_text: string[]
  confidence: number
  price_estimate: PriceEstimate
}

export type EbayDraft = {
  user_id: string
  category_id: string
  title: string
  description: string
  condition: string
  price: number
  currency: string
  item_specifics: Record<string, string[]>
}

/** Mirrors FastAPI `PostResponse` JSON (ISO-8601 date strings). */
export type Post = {
  id: string
  name: string
  created_at: string
  updated_at: string
  description?: string
  deleted_at: string | null
  listings: Listing[]
  /** Image URLs (same origin as the app when the UI is served from FastAPI). */
  image_urls: string[]
  analysis?: ProductAnalysis | null
  ebay_draft?: EbayDraft | null
}
