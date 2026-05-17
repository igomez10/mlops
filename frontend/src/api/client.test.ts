import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createPost, createPostWithImage, fetchEbaySession, updatePost } from './client'

function jsonResponse(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('createPost sends name and returns parsed post', async () => {
    const post = {
      id: '1',
      name: 'hello',
      created_at: '2020-01-01T00:00:00.000Z',
      updated_at: '2020-01-01T00:00:00.000Z',
      deleted_at: null,
      description: '',
      listings: [],
      image_urls: [],
    }
    vi.mocked(fetch).mockResolvedValue(jsonResponse(post, 201))

    const result = await createPost('hello')

    expect(result).toEqual(post)
    expect(fetch).toHaveBeenCalledWith('http://test.posts/posts', {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name: 'hello', description: '' }),
    })
  })

  it('createPostWithImage posts multipart to /posts', async () => {
    const out = {
      id: '1',
      name: 'p-abc',
      created_at: '2020-01-01T00:00:00.000Z',
      updated_at: '2020-01-01T00:00:00.000Z',
      deleted_at: null,
      description: 'A',
      listings: [],
      image_urls: ['https://x/a.png'],
    }
    vi.mocked(fetch).mockResolvedValue(jsonResponse(out, 201))
    const file = new File([new Uint8Array([1, 2, 3])], 'a.png', {
      type: 'image/png',
    })
    const result = await createPostWithImage('A', file)
    expect(result).toEqual(out)
    expect(fetch).toHaveBeenCalledTimes(1)
    const [, requestInit] = vi.mocked(fetch).mock.calls[0]
    expect(requestInit).toEqual(
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: expect.any(FormData),
      }),
    )
    const form = requestInit?.body as FormData
    expect(form.get('description')).toBe('A')
    expect(form.get('user_id')).toBeNull()
  })

  it('createPostWithImage preserves multi-item analysis and draft fields from /posts', async () => {
    const out = {
      id: 'multi-1',
      name: 'p-multi',
      created_at: '2020-01-01T00:00:00.000Z',
      updated_at: '2020-01-01T00:00:00.000Z',
      deleted_at: null,
      description: 'Bundle photo',
      listings: [
        {
          id: 'draft-1',
          marketplace_url: 'https://local.invalid/pending?item=0',
          image_url: 'https://x/a.png',
          created_at: '2020-01-01T00:00:00.000Z',
          status: 'draft',
          description: 'Apple AirPods Pro',
        },
        {
          id: 'draft-2',
          marketplace_url: 'https://local.invalid/pending?item=1',
          image_url: 'https://x/a.png',
          created_at: '2020-01-01T00:00:00.000Z',
          status: 'draft',
          description: 'Apple Watch Series 9',
        },
      ],
      image_urls: ['https://x/a.png'],
      analysis: {
        product_name: 'Apple AirPods Pro',
        brand: 'Apple',
        model: 'AirPods Pro',
        category: 'Earbud Headphones',
        condition_estimate: 'good',
        visible_text: ['Apple', 'AirPods Pro'],
        confidence: 0.96,
        price_estimate: {
          low: 110,
          high: 160,
          currency: 'USD',
          reasoning: 'r',
          comparable_sources: [],
        },
        detected_items: [
          {
            product_name: 'Apple AirPods Pro',
            brand: 'Apple',
            model: 'AirPods Pro',
            category: 'Earbud Headphones',
            condition_estimate: 'good',
            visible_text: ['Apple', 'AirPods Pro'],
            confidence: 0.96,
            price_estimate: {
              low: 110,
              high: 160,
              currency: 'USD',
              reasoning: 'r',
              comparable_sources: [],
            },
          },
          {
            product_name: 'Apple Watch Series 9',
            brand: 'Apple',
            model: 'Series 9',
            category: 'Smart Watches',
            condition_estimate: 'good',
            visible_text: ['Apple Watch'],
            confidence: 0.94,
            price_estimate: {
              low: 180,
              high: 240,
              currency: 'USD',
              reasoning: 'r',
              comparable_sources: [],
            },
          },
        ],
      },
      ebay_draft: {
        user_id: 'user-1',
        category_id: '9355',
        title: 'Apple AirPods Pro',
        description: 'Generated description',
        condition: 'USED_GOOD',
        price: 149.99,
        currency: 'USD',
        item_specifics: { Brand: ['Apple'] },
        draft_id: 'draft-a',
        source_image_url: 'https://x/a.png',
        analysis_index: 0,
        draft_count: 2,
      },
      ebay_drafts: [
        {
          user_id: 'user-1',
          category_id: '9355',
          title: 'Apple AirPods Pro',
          description: 'Generated description',
          condition: 'USED_GOOD',
          price: 149.99,
          currency: 'USD',
          item_specifics: { Brand: ['Apple'] },
          draft_id: 'draft-a',
          source_image_url: 'https://x/a.png',
          analysis_index: 0,
          draft_count: 2,
        },
        {
          user_id: 'user-1',
          category_id: '31387',
          title: 'Apple Watch Series 9',
          description: 'Generated description',
          condition: 'USED_GOOD',
          price: 219.99,
          currency: 'USD',
          item_specifics: { Brand: ['Apple'] },
          draft_id: 'draft-b',
          source_image_url: 'https://x/a.png',
          analysis_index: 1,
          draft_count: 2,
        },
      ],
    }
    vi.mocked(fetch).mockResolvedValue(jsonResponse(out, 201))

    const file = new File([new Uint8Array([1, 2, 3])], 'bundle.jpg', {
      type: 'image/jpeg',
    })
    const result = await createPostWithImage('Bundle photo', file)

    expect(result.analysis?.detected_items).toHaveLength(2)
    expect(result.ebay_drafts).toHaveLength(2)
    expect(result.ebay_drafts?.map((draft) => draft.title)).toEqual([
      'Apple AirPods Pro',
      'Apple Watch Series 9',
    ])
  })

  it('updatePost sends body object', async () => {
    const post = {
      id: 'a',
      name: 'renamed',
      created_at: '2020-01-01T00:00:00.000Z',
      updated_at: '2020-01-02T00:00:00.000Z',
      deleted_at: null,
      description: '',
      listings: [],
      image_urls: [],
    }
    vi.mocked(fetch).mockResolvedValue(jsonResponse(post, 200))

    const result = await updatePost('a', { name: 'renamed' })

    expect(result).toEqual(post)
    expect(fetch).toHaveBeenCalledWith('http://test.posts/posts/a', {
      method: 'PUT',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name: 'renamed' }),
    })
  })

  it('createPost surfaces error detail from JSON body', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: 'bad name' }, 400),
    )

    await expect(createPost('x')).rejects.toThrow('bad name')
  })

  it('fetchEbaySession includes credentials and returns parsed status', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ user_id: 'user-1', ebay_authenticated: true }, 200),
    )

    const result = await fetchEbaySession()

    expect(result).toEqual({ user_id: 'user-1', ebay_authenticated: true })
    expect(fetch).toHaveBeenCalledWith('http://test.posts/auth/ebay/session', {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
  })
})
