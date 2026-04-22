import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createPost, createPostWithImage, updatePost } from './client'

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
    expect(fetch).toHaveBeenCalledWith(
      'http://test.posts/posts',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      }),
    )
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
})
