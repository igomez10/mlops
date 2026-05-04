import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as client from '../api/client'
import type { Post } from '../types/post'
import { PostList } from './PostList'

vi.mock('../api/client', () => ({
  fetchPosts: vi.fn(),
  createPostWithImage: vi.fn(),
  updatePost: vi.fn(),
}))

function post(partial: Pick<Post, 'id' | 'name'> & Partial<Post>): Post {
  return {
    created_at: '2024-01-15T10:00:00.000Z',
    updated_at: '2024-01-15T10:00:00.000Z',
    deleted_at: null,
    description: '',
    listings: [],
    image_urls: [],
    ...partial,
  }
}

describe('PostList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.fetchPosts).mockReset()
    vi.mocked(client.createPostWithImage).mockReset()
    vi.mocked(client.updatePost).mockReset()
    vi.mocked(client.fetchPosts).mockResolvedValue([])
  })

  it('loads then shows empty state', async () => {
    render(<PostList />)

    expect(screen.getByTestId('posts-loading')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByTestId('posts-empty')).toBeInTheDocument()
    })
    expect(client.fetchPosts).toHaveBeenCalledTimes(1)
  })

  it('creates a post from the dialog and reloads the list', async () => {
    const user = userEvent.setup()
    const created = post({ id: 'n1', name: 'p-abc', description: 'From dialog' })
    vi.mocked(client.fetchPosts)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([created])
    vi.mocked(client.createPostWithImage).mockResolvedValue(created)

    render(<PostList />)
    await waitFor(() => screen.getByTestId('posts-empty'))

    await user.click(screen.getByTestId('post-new-open'))
    await user.type(
      screen.getByTestId('post-create-description'),
      'From dialog',
    )
    await user.type(screen.getByTestId('post-create-user-id'), 'user-123')
    const file = new File([new Uint8Array([1, 2, 3])], 'x.png', {
      type: 'image/png',
    })
    await user.upload(screen.getByTestId('post-create-image'), file)
    await user.click(screen.getByTestId('post-create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('posts-table')).toBeInTheDocument()
    })
    const row = screen.getByTestId('post-row')
    expect(within(row).getByTestId('post-name')).toHaveTextContent('From dialog')
    expect(client.createPostWithImage).toHaveBeenCalledWith('From dialog', file, {
      userId: 'user-123',
    })
    expect(client.fetchPosts).toHaveBeenCalledTimes(2)
  })

  it('updates a post and reloads the list', async () => {
    const user = userEvent.setup()
    const initial = post({ id: 'id-1', name: 'Before' })
    const afterList = [post({ id: 'id-1', name: 'After' })]
    vi.mocked(client.fetchPosts)
      .mockResolvedValueOnce([initial])
      .mockResolvedValueOnce(afterList)
    vi.mocked(client.updatePost).mockResolvedValue(afterList[0])

    render(<PostList />)
    await waitFor(() => screen.getByTestId('posts-table'))

    const row = screen.getByTestId('post-row')
    await user.click(within(row).getByTestId('post-edit'))
    const nameInput = within(row).getByTestId('post-edit-name')
    await user.clear(nameInput)
    await user.type(nameInput, 'After')
    await user.click(within(row).getByTestId('post-edit-save'))

    await waitFor(() => {
      expect(client.updatePost).toHaveBeenCalledWith('id-1', { name: 'After' })
    })
    expect(client.fetchPosts).toHaveBeenCalledTimes(2)
    expect(
      within(screen.getByTestId('post-row')).getByTestId('post-name'),
    ).toHaveTextContent('After')
  })

  it('expands to show read-only listings from the server', async () => {
    const user = userEvent.setup()
    const l1 = {
      id: 'L1',
      marketplace_url: 'https://a.com/1',
      image_url: 'https://i.com/1.jpg',
      created_at: '2024-01-15T10:00:00.000Z',
      status: 'draft',
      description: 'One',
    }
    const p = post({ id: 'p1', name: 'Shop', listings: [l1] })
    vi.mocked(client.fetchPosts).mockResolvedValue([p])

    render(<PostList />)
    await waitFor(() => screen.getByTestId('posts-table'))

    await user.click(screen.getByTestId('post-toggle-listings'))
    const panel = screen.getByTestId('post-listings-panel')
    expect(
      within(panel).getByTestId('post-listing-description'),
    ).toHaveTextContent('One')
    expect(within(panel).queryByTestId('post-add-listing-submit')).toBeNull()
  })

  it('shows analysis fields and ebay link when the listing is published', async () => {
    const user = userEvent.setup()
    const publishedListing = {
      id: 'L1',
      marketplace_url: 'https://www.ebay.com/itm/L1',
      image_url: 'https://i.com/1.jpg',
      created_at: '2024-01-15T10:00:00.000Z',
      status: 'PUBLISHED',
      description: 'Apple AirPods Pro',
    }
    const p = post({
      id: 'p-analysis',
      name: 'airpods',
      description: 'AirPods',
      listings: [publishedListing],
      analysis: {
        product_name: 'Apple AirPods Pro',
        brand: 'Apple',
        model: 'AirPods Pro',
        category: 'Earbud Headphones',
        condition_estimate: 'good',
        visible_text: ['AirPods', 'Apple'],
        confidence: 0.92,
        price_estimate: {
          low: 110,
          high: 160,
          currency: 'USD',
          reasoning: 'r',
          comparable_sources: [],
        },
      },
    })
    vi.mocked(client.fetchPosts).mockResolvedValue([p])

    render(<PostList />)
    await waitFor(() => screen.getByTestId('posts-table'))

    const row = screen.getByTestId('post-row')
    expect(within(row).getByTestId('post-ebay-link')).toHaveAttribute(
      'href',
      'https://www.ebay.com/itm/L1',
    )

    await user.click(screen.getByTestId('post-toggle-listings'))
    const panel = screen.getByTestId('post-listings-panel')
    expect(within(panel).getByTestId('post-analysis-product-name')).toHaveTextContent(
      'Apple AirPods Pro',
    )
    expect(within(panel).getByTestId('post-analysis-price')).toHaveTextContent(
      'USD 110–160',
    )
    expect(within(panel).getByTestId('post-analysis-ebay-link')).toHaveAttribute(
      'href',
      'https://www.ebay.com/itm/L1',
    )
  })
})
