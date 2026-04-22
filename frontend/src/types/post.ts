/** Mirrors FastAPI `ListingResponse` / embedded listing JSON. */
export type Listing = {
  id: string
  marketplace_url: string
  image_url: string
  created_at: string
  status: string
  description: string
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
  /** Full HTTPS URLs of images uploaded for this post (GCS public URLs). */
  image_urls: string[]
}
