import {
  Fragment,
  type FormEvent,
  useCallback,
  useEffect,
  useId,
  useState,
} from 'react'
import { createPostWithImage, fetchPosts, updatePost } from '../api/client'
import type { Post } from '../types/post'

/** ISO instant → e.g. "10 minutes ago" (uses browser locale). */
function formatRelativeWhen(iso: string, at: Date): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) {
    return iso
  }
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  const diffSec = (d.getTime() - at.getTime()) / 1000
  const a = Math.abs(diffSec)
  if (a < 60) {
    return rtf.format(Math.round(diffSec), 'second')
  }
  if (a < 3600) {
    return rtf.format(Math.round(diffSec / 60), 'minute')
  }
  if (a < 86400) {
    return rtf.format(Math.round(diffSec / 3600), 'hour')
  }
  if (a < 604800) {
    return rtf.format(Math.round(diffSec / 86400), 'day')
  }
  if (a < 2_629_800) {
    return rtf.format(Math.round(diffSec / 604800), 'week')
  }
  if (a < 31_536_000) {
    return rtf.format(Math.round(diffSec / 2_629_800), 'month')
  }
  return rtf.format(Math.round(diffSec / 31_536_000), 'year')
}

const absoluteFmt = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatAbsoluteWhen(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : absoluteFmt.format(d)
}

function postListings(p: Post) {
  return p.listings ?? []
}

function postImageUrls(p: Post) {
  return p.image_urls ?? []
}

/** Primary line in the list: user description, or internal name. */
function postLabel(p: Post) {
  const d = p.description?.trim()
  if (d) return d
  return p.name
}

export function PostList() {
  const titleId = useId()
  const [now, setNow] = useState(() => new Date())
  const [posts, setPosts] = useState<Post[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [createDescription, setCreateDescription] = useState('')
  const [createImage, setCreateImage] = useState<File | null>(null)
  const [creating, setCreating] = useState(false)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [savingId, setSavingId] = useState<string | null>(null)

  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set())

  const loadPosts = useCallback(async () => {
    setLoadError(null)
    try {
      const data = await fetchPosts()
      setPosts(data)
    } catch (e: unknown) {
      setPosts(null)
      setLoadError(e instanceof Error ? e.message : 'Failed to load posts')
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch; state updates run after await
    void loadPosts()
  }, [loadPosts])

  useEffect(() => {
    const t = window.setInterval(() => setNow(() => new Date()), 60_000)
    return () => window.clearInterval(t)
  }, [])

  function toggleListingsOpen(postId: string) {
    setExpandedIds((prev) => {
      const n = new Set(prev)
      if (n.has(postId)) n.delete(postId)
      else n.add(postId)
      return n
    })
  }

  function openCreate() {
    setActionError(null)
    setCreateDescription('')
    setCreateImage(null)
    setCreateOpen(true)
  }

  function closeCreate() {
    if (!creating) setCreateOpen(false)
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!createDescription.trim() || !createImage) {
      setActionError('Add a short description and choose a photo of your item.')
      return
    }
    setActionError(null)
    setCreating(true)
    try {
      await createPostWithImage(createDescription.trim(), createImage)
      setCreateOpen(false)
      setCreateDescription('')
      setCreateImage(null)
      await loadPosts()
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  function startEdit(p: Post) {
    setActionError(null)
    setEditingId(p.id)
    setEditName(postLabel(p))
  }

  function cancelEdit() {
    setEditingId(null)
    setEditName('')
  }

  async function handleSaveEdit(p: Post) {
    const text = editName.trim()
    if (!text) return
    setActionError(null)
    setSavingId(p.id)
    try {
      if (p.description?.trim()) {
        await updatePost(p.id, { name: p.name, description: text })
      } else {
        await updatePost(p.id, { name: text })
      }
      setEditingId(null)
      setEditName('')
      await loadPosts()
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setSavingId(null)
    }
  }

  const busy = !!savingId

  return (
    <div className="post-list">
      <div className="post-list-toolbar">
        <h2 className="post-list-title">Your scans</h2>
        <button
          type="button"
          className="post-new-button"
          onClick={openCreate}
          data-testid="post-new-open"
        >
          Scan new photo
        </button>
      </div>

      {createOpen ? (
        <div
          className="post-create-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          data-testid="post-create-dialog"
        >
          <form
            className="post-create-dialog-panel"
            onSubmit={handleCreate}
            data-testid="post-create-form"
          >
            <div className="post-create-dialog-header">
              <h2 className="post-create-dialog-title" id={titleId}>
                Scan &amp; detect items
              </h2>
            </div>
            <div className="post-create-dialog-body">
              <div className="post-create-scan-hint">
                <span className="post-create-scan-dot" aria-hidden="true" />
                AI will detect each item separately from your photo.
              </div>
              <label className="post-create-label" htmlFor="post-create-description">
                What are you selling?
              </label>
              <textarea
                id="post-create-description"
                className="post-create-textarea"
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                rows={4}
                disabled={creating}
                placeholder="e.g. Moving boxes from living room — vintage lamp, blu-ray collection, desk accessories"
                data-testid="post-create-description"
              />
              <label className="post-create-label" htmlFor="post-create-image">
                Your photo (multiple items OK)
              </label>
              <div className="post-create-dropzone">
                <input
                  id="post-create-image"
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  disabled={creating}
                  data-testid="post-create-image"
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null
                    setCreateImage(f)
                  }}
                />
              </div>
              <div className="post-create-dialog-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={closeCreate}
                  disabled={creating}
                  data-testid="post-create-cancel"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    creating || !createDescription.trim() || !createImage
                  }
                  data-testid="post-create-submit"
                >
                  {creating ? 'Scanning…' : 'Scan & detect items'}
                </button>
              </div>
              <p className="post-create-hint muted">
                We'll scan your photo for individual items and create a separate
                listing for each one found.
              </p>
            </div>
          </form>
        </div>
      ) : null}

      {actionError ? (
        <div className="banner error" role="alert" data-testid="posts-action-error">
          {actionError}
        </div>
      ) : null}

      {loadError ? (
        <div className="banner error" role="alert" data-testid="posts-error">
          {loadError}
        </div>
      ) : null}

      {posts === null && !loadError ? (
        <p className="muted" data-testid="posts-loading">
          Loading your items…
        </p>
      ) : null}

      {posts && posts.length === 0 ? (
        <p className="empty" data-testid="posts-empty">
          No scans yet. Tap <strong>Scan new photo</strong> — one photo can
          create dozens of listings.
        </p>
      ) : null}

      {posts && posts.length > 0 ? (
        <div className="table-wrap">
          <table data-testid="posts-table">
            <caption className="sr-only">Your items and eBay listings</caption>
            <thead>
              <tr>
                <th scope="col" className="col-expand">
                  <span className="sr-only">Listings</span>
                </th>
                <th scope="col">Item</th>
                <th scope="col">Created</th>
                <th scope="col">Updated</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {posts.map((p) => {
                const listings = postListings(p)
                const images = postImageUrls(p)
                const isOpen = expandedIds.has(p.id)
                return (
                  <Fragment key={p.id}>
                    <tr data-testid="post-row" data-post-id={p.id}>
                      <td className="col-expand">
                        <button
                          type="button"
                          className="expand-listings"
                          onClick={() => toggleListingsOpen(p.id)}
                          aria-expanded={isOpen}
                          aria-controls={`post-listings-panel-${p.id}`}
                          data-testid="post-toggle-listings"
                          data-post-id={p.id}
                          disabled={busy}
                        >
                          {isOpen ? '▼' : '▶'}{' '}
                          <span
                            className="listing-count"
                            data-testid="post-listing-count"
                          >
                            {listings.length}
                          </span>
                        </button>
                      </td>
                      <td data-testid="post-name">
                        {editingId === p.id ? (
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            aria-label="Edit post"
                            data-testid="post-edit-name"
                          />
                        ) : (
                          postLabel(p)
                        )}
                      </td>
                      <td
                        data-testid="post-created"
                        title={formatAbsoluteWhen(p.created_at)}
                      >
                        {formatRelativeWhen(p.created_at, now)}
                      </td>
                      <td
                        data-testid="post-updated"
                        title={formatAbsoluteWhen(p.updated_at)}
                      >
                        {formatRelativeWhen(p.updated_at, now)}
                      </td>
                      <td data-testid="post-status">
                        {p.deleted_at ? (
                          <span className="badge deleted" title={p.deleted_at}>
                            Deleted
                          </span>
                        ) : (
                          <span className="badge active">Active</span>
                        )}
                      </td>
                      <td className="actions">
                        {editingId === p.id ? (
                          <div className="action-buttons">
                            <button
                              type="button"
                              onClick={() => handleSaveEdit(p)}
                              disabled={savingId === p.id || !editName.trim()}
                              data-testid="post-edit-save"
                            >
                              {savingId === p.id ? 'Saving…' : 'Save'}
                            </button>
                            <button
                              type="button"
                              className="secondary"
                              onClick={cancelEdit}
                              disabled={savingId === p.id}
                              data-testid="post-edit-cancel"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="action-buttons">
                            <button
                              type="button"
                              onClick={() => startEdit(p)}
                              disabled={busy || !!editingId}
                              data-testid="post-edit"
                            >
                              Edit
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {isOpen ? (
                      <tr
                        className="post-listings-row"
                        data-testid="post-listings-row"
                        data-post-id={p.id}
                      >
                        <td colSpan={6}>
                          <div
                            id={`post-listings-panel-${p.id}`}
                            className="post-listings-panel"
                            data-testid="post-listings-panel"
                          >
                            {p.description?.trim() ? (
                              <p
                                className="post-body-description"
                                data-testid="post-body-description"
                              >
                                {p.description.trim()}
                              </p>
                            ) : null}
                            <div className="post-images-block">
                              <h4 className="post-images-heading">Your photos</h4>
                              {images.length === 0 ? (
                                <p
                                  className="muted post-images-empty"
                                  data-testid="post-images-empty"
                                >
                                  No images.
                                </p>
                              ) : (
                                <div
                                  className="post-images-grid"
                                  data-testid="post-images-grid"
                                >
                                  {images.map((url) => (
                                    <a
                                      key={url}
                                      href={url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="post-image-thumb-wrap"
                                      data-testid="post-image-thumb"
                                    >
                                      <img
                                        src={url}
                                        alt=""
                                        className="post-image-thumb"
                                      />
                                    </a>
                                  ))}
                                </div>
                              )}
                            </div>
                            <h4 className="post-listings-heading">eBay listings we manage</h4>
                            {listings.length === 0 ? (
                              <p
                                className="muted"
                                data-testid="post-listings-empty"
                              >
                                No listings.
                              </p>
                            ) : (
                              <ul
                                className="post-listing-pods"
                                data-testid="post-listing-items"
                              >
                                {listings.map((L) => (
                                  <li
                                    key={L.id}
                                    className="post-listing-pod"
                                    data-testid="post-listing-item"
                                  >
                                    <div className="post-listing-pod-media">
                                      {L.image_url ? (
                                        <img
                                          src={L.image_url}
                                          alt=""
                                          data-testid="post-listing-image"
                                        />
                                      ) : (
                                        <div
                                          className="post-listing-pod-placeholder"
                                          data-testid="post-listing-image"
                                        />
                                      )}
                                    </div>
                                    <div className="post-listing-pod-body">
                                      <span
                                        className="post-listing-pod-status"
                                        data-testid="post-listing-status"
                                      >
                                        {L.status}
                                      </span>
                                      <p
                                        className="post-listing-pod-desc"
                                        data-testid="post-listing-description"
                                        title={
                                          L.description
                                            ? L.description
                                            : undefined
                                        }
                                      >
                                        {L.description || '—'}
                                      </p>
                                      {L.marketplace_url ? (
                                        <a
                                          href={L.marketplace_url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="post-listing-pod-link"
                                          data-testid="post-listing-marketplace-link"
                                        >
                                          Open
                                        </a>
                                      ) : null}
                                      <time
                                        className="post-listing-pod-time muted"
                                        data-testid="post-listing-created"
                                        dateTime={L.created_at}
                                        title={formatAbsoluteWhen(
                                          L.created_at,
                                        )}
                                      >
                                        {formatRelativeWhen(
                                          L.created_at,
                                          now,
                                        )}
                                      </time>
                                    </div>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
