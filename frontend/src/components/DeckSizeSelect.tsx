interface DeckSizeSelectProps {
  value: number;
  onChange: (topics: number) => void;
  disabled?: boolean;
}

export function DeckSizeSelect({ value, onChange, disabled }: DeckSizeSelectProps) {
  return (
    <label className="flex items-center gap-3 text-sm">
      Deck size
      <select aria-label="Deck size" value={value} disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="rounded-md border border-input bg-background px-3 py-2">
        <option value={4}>Starter: 4 topics (faster)</option>
        <option value={8}>Standard: 8 topics</option>
        <option value={12}>Detailed: 12 topics</option>
      </select>
    </label>
  );
}
