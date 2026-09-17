import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import UploadPage from './UploadPage';
import { documentsApi, generateFlashcards } from '@/services/api';

vi.mock('@/services/api', () => ({
  documentsApi: { upload: vi.fn() },
  generateFlashcards: vi.fn(),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

async function upload() {
  vi.mocked(documentsApi.upload).mockResolvedValue({ data: { document: { id: 21 } } } as never);
  render(<MemoryRouter initialEntries={['/instances/1/upload']}>
    <Routes><Route path="/instances/:id/upload" element={<UploadPage />} /></Routes>
  </MemoryRouter>);
  fireEvent.drop(screen.getByText('Drop files here or click to browse').parentElement!, {
    dataTransfer: { files: [new File(['Neurons learn weights.'], 'notes.pdf', { type: 'application/pdf' })] },
  });
  await screen.findByRole('button', { name: 'Generate Flashcards' });
}

it('generates a starter deck from the uploaded document', async () => {
  vi.mocked(generateFlashcards).mockResolvedValue({ cards_created: 3, warnings: [] } as never);
  await upload();
  fireEvent.click(screen.getByRole('button', { name: 'Generate Flashcards' }));
  await screen.findByText('3 flashcards generated');
  expect(generateFlashcards).toHaveBeenCalledWith('1', expect.any(Function), 4, 21);
});

it('keeps the document available to retry after generation fails', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.mocked(generateFlashcards).mockRejectedValueOnce(new Error('Provider unavailable'));
  await upload();
  fireEvent.click(screen.getByRole('button', { name: 'Generate Flashcards' }));
  await screen.findByText('Provider unavailable');
  expect(screen.getByRole('button', { name: 'Retry Generation' })).toBeEnabled();
  expect(documentsApi.upload).toHaveBeenCalledTimes(1);
  vi.restoreAllMocks();
});

it('shows warnings when no cards were produced', async () => {
  vi.mocked(generateFlashcards).mockResolvedValue({ cards_created: 0, warnings: ['No sources found'] } as never);
  await upload();
  fireEvent.change(screen.getByRole('combobox', { name: 'Deck size' }), { target: { value: '8' } });
  fireEvent.click(screen.getByRole('button', { name: 'Generate Flashcards' }));
  await waitFor(() => expect(screen.getByText('No sources found')).toBeInTheDocument());
  expect(screen.queryByText('0 flashcards generated')).not.toBeInTheDocument();
  expect(generateFlashcards).toHaveBeenCalledWith('1', expect.any(Function), 8, 21);
});
