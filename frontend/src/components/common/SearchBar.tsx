interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  id?: string;
}

export function SearchBar({ value, onChange, placeholder, id = "search-input" }: SearchBarProps) {
  return (
    <div className="search-bar">
      <label htmlFor={id} className="sr-only">
        Search anime
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "Search anime titles…"}
      />
    </div>
  );
}
