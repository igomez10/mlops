/** Mirrors FastAPI `PostResponse` JSON (ISO-8601 date strings). */
export type Post = {
  id: string
  name: string
  created_at: string
  updated_at: string
  deleted_at: string | null
}
