import {
  Fragment,
  type FormEvent,
  useCallback,
  useEffect,
  useId,
  useState,
} from 'react'
import {
  createPostWithImage,
  fetchPosts,
  publishEbayListing,
  updateEbayDraft,
  updatePost,
} from '../api/client'
import type { EbayDraft, Post } from '../types/post'

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

function postAnalysis(p: Post) {
  return p.analysis ?? null
}

function publishedListing(p: Post) {
  return postListings(p).find((listing) => {
    const status = listing.status?.toLowerCase() ?? ''
    return status.includes('publish') || status.includes('active')
  }) ?? null
}

function formatPriceRange(p: Post) {
  const analysis = postAnalysis(p)
  const price = analysis?.price_estimate
  if (!price) return null
  const currency = price.currency?.trim() || 'USD'
  if (price.low > 0 && price.high > 0) {
    return `${currency} ${price.low}–${price.high}`
  }
  if (price.high > 0) return `${currency} ${price.high}`
  if (price.low > 0) return `${currency} ${price.low}`
  return null
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
  const [createUserId, setCreateUserId] = useState('')
  const [creating, setCreating] = useState(false)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [savingId, setSavingId] = useState<string | null>(null)

  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set())

  const [draftEdits, setDraftEdits] = useState<
    Record<string, Partial<EbayDraft>>
  >({})
  const [savingDraftId, setSavingDraftId] = useState<string | null>(null)
  const [publishingId, setPublishingId] = useState<string | null>(null)

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
    setCreateUserId('')
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
      await createPostWithImage(createDescription.trim(), createImage, {
        userId: createUserId.trim() || undefined,
      })
      setCreateOpen(false)
      setCreateDescription('')
      setCreateImage(null)
      setCreateUserId('')
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

  function getDraftEdit(p: Post): Partial<EbayDraft> {
    return draftEdits[p.id] ?? (p.ebay_draft ?? {})
  }

  function setDraftField<K extends keyof EbayDraft>(
    postId: string,
    base: EbayDraft,
    key: K,
    value: EbayDraft[K],
  ) {
    setDraftEdits((prev) => ({
      ...prev,
      [postId]: { ...(prev[postId] ?? base), [key]: value },
    }))
  }

  function setItemSpecific(
    postId: string,
    base: EbayDraft,
    name: string,
    value: string,
  ) {
    setDraftEdits((prev) => {
      const existing = prev[postId] ?? base
      return {
        ...prev,
        [postId]: {
          ...existing,
          item_specifics: {
            ...(existing.item_specifics ?? base.item_specifics),
            [name]: [value],
          },
        },
      }
    })
  }

  async function handleSaveDraft(p: Post) {
    const edits = draftEdits[p.id]
    if (!edits) return
    setActionError(null)
    setSavingDraftId(p.id)
    try {
      const updated = await updateEbayDraft(p.id, edits)
      setPosts((prev) => prev?.map((x) => (x.id === p.id ? updated : x)) ?? prev)
      setDraftEdits((prev) => {
        const n = { ...prev }
        delete n[p.id]
        return n
      })
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Save draft failed')
    } finally {
      setSavingDraftId(null)
    }
  }

  async function handlePublish(p: Post) {
    setActionError(null)
    setPublishingId(p.id)
    try {
      const updated = await publishEbayListing(p.id)
      setPosts((prev) => prev?.map((x) => (x.id === p.id ? updated : x)) ?? prev)
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Publish failed')
    } finally {
      setPublishingId(null)
    }
  }

  const busy = !!savingId

  return (
    <div className="post-list">
      <div className="post-list-toolbar">
        <h2 className="post-list-title">Your items</h2>
        <button
          type="button"
          className="post-new-button"
          onClick={openCreate}
          data-testid="post-new-open"
        >
          List an item
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
            <h2 className="post-create-dialog-title" id={titleId}>
              List an item
            </h2>
            <label className="post-create-label" htmlFor="post-create-description">
              Description
            </label>
            <textarea
              id="post-create-description"
              className="post-create-textarea"
              value={createDescription}
              onChange={(e) => setCreateDescription(e.target.value)}
              rows={4}
              disabled={creating}
              placeholder="Condition, what's included, any flaws…"
              data-testid="post-create-description"
            />
            <label className="post-create-label" htmlFor="post-create-image">
              Image
            </label>
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
            <label className="post-create-label" htmlFor="post-create-user-id">
              eBay user ID
            </label>
            <input
              id="post-create-user-id"
              type="text"
              className="post-create-input"
              value={createUserId}
              onChange={(e) => setCreateUserId(e.target.value)}
              disabled={creating}
              placeholder="Optional: enables automatic eBay publish"
              data-testid="post-create-user-id"
            />
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
                {creating ? 'Uploading…' : 'Add to my items'}
              </button>
            </div>
            <p className="post-create-hint muted">
              We upload your photo securely first, then save your item so we can
              prepare your eBay listing. Add an eBay user ID if you want us to
              publish it immediately after analysis.
            </p>
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
          No items yet. Tap <strong>List an item</strong> to upload a photo and
          description—we’ll take it from there on eBay.
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
                const analysis = postAnalysis(p)
                const ebayListing = publishedListing(p)
                const priceRange = formatPriceRange(p)
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
                          <div className="post-name-cell">
                            <span>{postLabel(p)}</span>
                            {analysis ? (
                              <span
                                className="post-analysis-badge"
                                data-testid="post-analysis-badge"
                                title={[
                                  analysis.brand,
                                  analysis.product_name,
                                  analysis.model,
                                ].filter(Boolean).join(' · ')}
                              >
                                {[
                                  analysis.brand,
                                  analysis.product_name,
                                  analysis.model,
                                ].filter(Boolean).join(' · ')}
                              </span>
                            ) : null}
                          </div>
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
                        ) : ebayListing ? (
                          <a
                            className="badge link"
                            href={ebayListing.marketplace_url}
                            target="_blank"
                            rel="noreferrer"
                            data-testid="post-ebay-link"
                          >
                            Live on eBay
                          </a>
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
                            <div className="post-analysis-block">
                              <div className="post-section-heading-row">
                                <h4 className="post-analysis-heading">Product analysis</h4>
                                {ebayListing ? (
                                  <a
                                    href={ebayListing.marketplace_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="post-analysis-ebay-link"
                                    data-testid="post-analysis-ebay-link"
                                  >
                                    View eBay listing
                                  </a>
                                ) : null}
                              </div>
                              {analysis ? (
                                <div
                                  className="post-analysis-grid"
                                  data-testid="post-analysis-grid"
                                >
                                  <div className="post-analysis-card">
                                    <span className="post-analysis-label">Product</span>
                                    <strong data-testid="post-analysis-product-name">
                                      {analysis.product_name || '—'}
                                    </strong>
                                  </div>
                                  <div className="post-analysis-card">
                                    <span className="post-analysis-label">Brand</span>
                                    <strong>{analysis.brand || '—'}</strong>
                                  </div>
                                  <div className="post-analysis-card">
                                    <span className="post-analysis-label">Model</span>
                                    <strong>{analysis.model || '—'}</strong>
                                  </div>
                                  <div className="post-analysis-card">
                                    <span className="post-analysis-label">Category</span>
                                    <strong>{analysis.category || '—'}</strong>
                                  </div>
                                  <div className="post-analysis-card">
                                    <span className="post-analysis-label">Condition</span>
                                    <strong>{analysis.condition_estimate || '—'}</strong>
                                  </div>
                                  <div className="post-analysis-card">
                                    <span className="post-analysis-label">Price estimate</span>
                                    <strong data-testid="post-analysis-price">
                                      {priceRange || '—'}
                                    </strong>
                                  </div>
                                  <div className="post-analysis-card">
                                    <span className="post-analysis-label">Confidence</span>
                                    <strong>
                                      {Number.isFinite(analysis.confidence)
                                        ? `${Math.round(analysis.confidence * 100)}%`
                                        : '—'}
                                    </strong>
                                  </div>
                                  <div className="post-analysis-card post-analysis-card-wide">
                                    <span className="post-analysis-label">Visible text</span>
                                    <strong>
                                      {analysis.visible_text?.length
                                        ? analysis.visible_text.join(', ')
                                        : '—'}
                                    </strong>
                                  </div>
                                </div>
                              ) : (
                                <p className="muted" data-testid="post-analysis-empty">
                                  No product analysis available yet.
                                </p>
                              )}
                            </div>
                            {p.ebay_draft ? (() => {
                              const draft = p.ebay_draft
                              const edit = getDraftEdit(p) as Partial<EbayDraft>
                              const isSaving = savingDraftId === p.id
                              const isPublishing = publishingId === p.id
                              const hasEdits = !!draftEdits[p.id]
                              const specifics = edit.item_specifics ?? draft.item_specifics ?? {}
                              return (
                                <div className="post-ebay-draft-block" data-testid="post-ebay-draft">
                                  <div className="post-section-heading-row">
                                    <h4 className="post-ebay-draft-heading">eBay listing draft</h4>
                                    <div className="post-ebay-draft-actions">
                                      {hasEdits ? (
                                        <button
                                          type="button"
                                          className="secondary"
                                          onClick={() => handleSaveDraft(p)}
                                          disabled={isSaving || isPublishing}
                                          data-testid="post-ebay-draft-save"
                                        >
                                          {isSaving ? 'Saving…' : 'Save changes'}
                                        </button>
                                      ) : null}
                                      <button
                                        type="button"
                                        onClick={() => handlePublish(p)}
                                        disabled={isSaving || isPublishing || hasEdits}
                                        data-testid="post-ebay-draft-publish"
                                      >
                                        {isPublishing ? 'Publishing…' : 'Publish on eBay'}
                                      </button>
                                    </div>
                                  </div>
                                  <div className="post-ebay-draft-grid">
                                    <label className="post-ebay-draft-label" htmlFor={`draft-title-${p.id}`}>Title</label>
                                    <input
                                      id={`draft-title-${p.id}`}
                                      type="text"
                                      className="post-ebay-draft-input"
                                      value={edit.title ?? draft.title}
                                      onChange={(e) => setDraftField(p.id, draft, 'title', e.target.value)}
                                      disabled={isSaving || isPublishing}
                                      data-testid="post-ebay-draft-title"
                                    />
                                    <label className="post-ebay-draft-label" htmlFor={`draft-condition-${p.id}`}>Condition</label>
                                    <input
                                      id={`draft-condition-${p.id}`}
                                      type="text"
                                      className="post-ebay-draft-input"
                                      value={edit.condition ?? draft.condition}
                                      onChange={(e) => setDraftField(p.id, draft, 'condition', e.target.value)}
                                      disabled={isSaving || isPublishing}
                                      data-testid="post-ebay-draft-condition"
                                    />
                                    <label className="post-ebay-draft-label" htmlFor={`draft-price-${p.id}`}>
                                      Price ({edit.currency ?? draft.currency})
                                    </label>
                                    <input
                                      id={`draft-price-${p.id}`}
                                      type="number"
                                      min="0"
                                      step="0.01"
                                      className="post-ebay-draft-input"
                                      value={edit.price ?? draft.price}
                                      onChange={(e) => setDraftField(p.id, draft, 'price', parseFloat(e.target.value) || 0)}
                                      disabled={isSaving || isPublishing}
                                      data-testid="post-ebay-draft-price"
                                    />
                                    {Object.entries(specifics).map(([name, vals]) => (
                                      <Fragment key={name}>
                                        <label className="post-ebay-draft-label" htmlFor={`draft-spec-${p.id}-${name}`}>
                                          {name}
                                        </label>
                                        <input
                                          id={`draft-spec-${p.id}-${name}`}
                                          type="text"
                                          className="post-ebay-draft-input"
                                          value={vals[0] ?? ''}
                                          onChange={(e) => setItemSpecific(p.id, draft, name, e.target.value)}
                                          disabled={isSaving || isPublishing}
                                          data-testid={`post-ebay-draft-spec-${name.toLowerCase().replace(/\s+/g, '-')}`}
                                        />
                                      </Fragment>
                                    ))}
                                  </div>
                                </div>
                              )
                            })() : null}
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
