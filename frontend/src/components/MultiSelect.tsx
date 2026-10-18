import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type JSX,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { useT } from "../i18n";
import { MAX_FILTER_VALUES } from "../lib/reportQuery";

export interface MultiSelectOptions {
  items: string[];
  truncated: boolean;
}

export interface MultiSelectProps {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  loadOptions: (q: string, signal: AbortSignal) => Promise<MultiSelectOptions>;
  reloadKey?: string;
  max?: number;
  hint?: string;
  id?: string;
  disabled?: boolean;
  className?: string;
}

type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; items: string[]; truncated: boolean }
  | { status: "error" };

export function MultiSelect({
  label,
  values,
  onChange,
  loadOptions,
  reloadKey = "",
  max = MAX_FILTER_VALUES,
  hint,
  id,
  disabled = false,
  className,
}: MultiSelectProps): JSX.Element {
  const t = useT();
  const autoId = useId();
  const inputId = id ?? `multiselect-input-${autoId}`;
  const listboxId = `multiselect-listbox-${autoId}`;
  const statusId = `multiselect-status-${autoId}`;
  const hintId = hint ? `multiselect-hint-${autoId}` : undefined;

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [state, setState] = useState<LoadState>({ status: "idle" });

  const cacheRef = useRef<{
    key: string;
    q: string;
    items: string[];
    truncated: boolean;
  } | null>(null);

  const cancelPending = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (debounceRef.current !== null) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      cancelPending();
    };
  }, [cancelPending]);

  useEffect(() => {
    cacheRef.current = null;
  }, [reloadKey]);

  const runQuery = useCallback(
    async (q: string, signal: AbortSignal) => {
      const trimmed = q.trim();
      const cached = cacheRef.current;
      if (cached && cached.key === reloadKey && cached.q === trimmed) {
        setState({ status: "success", items: cached.items, truncated: cached.truncated });
        return;
      }
      setState({ status: "loading" });
      try {
        const result = await loadOptions(trimmed, signal);
        if (signal.aborted) return;
        cacheRef.current = {
          key: reloadKey,
          q: trimmed,
          items: result.items,
          truncated: result.truncated,
        };
        setState({ status: "success", items: result.items, truncated: result.truncated });
      } catch (error) {
        if (signal.aborted) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ status: "error" });
      }
    },
    [loadOptions, reloadKey],
  );

  const openAndLoad = useCallback(() => {
    setOpen(true);
    const trimmed = query.trim();
    const cached = cacheRef.current;
    if (cached && cached.key === reloadKey && cached.q === trimmed) {
      setState({ status: "success", items: cached.items, truncated: cached.truncated });
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    void runQuery(query, controller.signal);
  }, [query, reloadKey, runQuery]);

  const closeList = useCallback(() => {
    setOpen(false);
    setActiveIndex(0);
    cancelPending();
  }, [cancelPending]);

  const handleInputChange = (value: string) => {
    setQuery(value);
    setOpen(true);
    setActiveIndex(0);
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    const trimmed = value.trim();
    if (trimmed === "") {
      const cached = cacheRef.current;
      if (cached && cached.key === reloadKey && cached.q === "") {
        setState({ status: "success", items: cached.items, truncated: cached.truncated });
        return;
      }
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      void runQuery("", controller.signal);
      return;
    }
    debounceRef.current = setTimeout(() => {
      debounceRef.current = null;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      void runQuery(value, controller.signal);
    }, 250);
  };

  const toggleValue = (value: string) => {
    if (disabled) return;
    if (values.includes(value)) {
      onChange(values.filter((v) => v !== value));
      return;
    }
    if (values.length >= max) return;
    onChange([...values, value]);
  };

  const handleOptionClick = (value: string) => {
    toggleValue(value);
  };

  const handleOptionMouseDown = (event: MouseEvent) => {
    event.preventDefault();
  };

  const handleInputFocus = () => {
    if (!open) openAndLoad();
  };

  const handleInputClick = () => {
    if (!open) openAndLoad();
  };

  const handleWrapperBlur = (event: FocusEvent) => {
    if (wrapperRef.current?.contains(event.relatedTarget as Node)) return;
    closeList();
  };

  const items = state.status === "success" ? state.items : [];
  const truncated = state.status === "success" ? state.truncated : false;

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return;

    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        if (!open) {
          openAndLoad();
          return;
        }
        setActiveIndex((prev) => (items.length === 0 ? 0 : (prev + 1) % items.length));
        break;
      case "ArrowUp":
        event.preventDefault();
        if (!open) {
          openAndLoad();
          return;
        }
        setActiveIndex((prev) =>
          items.length === 0 ? 0 : (prev - 1 + items.length) % items.length,
        );
        break;
      case "Home":
        if (open && items.length > 0) {
          event.preventDefault();
          setActiveIndex(0);
        }
        break;
      case "End":
        if (open && items.length > 0) {
          event.preventDefault();
          setActiveIndex(items.length - 1);
        }
        break;
      case "Enter":
        if (open) {
          event.preventDefault();
          if (items.length > 0) {
            toggleValue(items[activeIndex] ?? "");
          }
        }
        break;
      case "Escape":
        if (open) {
          event.preventDefault();
          event.stopPropagation();
          closeList();
          inputRef.current?.focus();
        }
        break;
      case "Backspace":
        if (query === "" && values.length > 0) {
          event.preventDefault();
          onChange(values.slice(0, -1));
        }
        break;
      case "Tab":
        closeList();
        break;
      default:
        break;
    }
  };

  const handleClearAll = () => {
    onChange([]);
  };

  const statusText = (() => {
    if (!open) return "";
    if (state.status === "loading") return t.common.loading;
    if (state.status === "error") return t.multiSelect.error;
    if (items.length === 0) {
      return query.trim() === "" ? t.multiSelect.noValues : t.multiSelect.noMatches;
    }
    if (values.length >= max) return t.multiSelect.limit(max);
    if (truncated) return t.multiSelect.truncated;
    return "";
  })();

  const statusClasses =
    state.status === "error" ? "text-danger" : "text-ink-soft";

  return (
    <div className={className} ref={wrapperRef} onBlur={handleWrapperBlur}>
      <div className="mb-1.5 flex items-baseline gap-0.5">
        <label htmlFor={inputId} className="block text-sm font-semibold text-ink-2">
          {label}
        </label>
      </div>

      {values.length > 0 && (
        <ul
          aria-label={t.multiSelect.selected(label)}
          className="mb-2 flex flex-wrap gap-1.5"
        >
          {values.map((value) => (
            <li key={value} className="max-w-full">
              <button
                type="button"
                aria-label={t.multiSelect.remove(value)}
                onClick={() => toggleValue(value)}
                disabled={disabled}
                className="flex min-h-tap min-w-tap max-w-full items-center gap-1 rounded-full bg-accent-soft px-3 py-1 text-left text-xs font-semibold text-accent ring-1 ring-inset ring-accent-line transition-colors hover:bg-accent-soft-2 hover:text-accent-deep disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="min-w-0 [overflow-wrap:anywhere]">{value}</span>
                <X aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
              </button>
            </li>
          ))}
          {values.length >= 2 && (
            <li className="flex items-center">
              <button
                type="button"
                onClick={handleClearAll}
                disabled={disabled}
                className="min-h-tap rounded-lg px-2 text-sm font-semibold text-ink-soft transition-colors hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t.multiSelect.clearAll}
              </button>
            </li>
          )}
        </ul>
      )}

      <div className="relative">
        <input
          ref={inputRef}
          id={inputId}
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={
            open && items.length > 0 ? `${listboxId}-option-${activeIndex}` : undefined
          }
          aria-describedby={[hintId, statusId].filter(Boolean).join(" ") || undefined}
          type="text"
          value={query}
          disabled={disabled}
          placeholder={
            values.length === 0 && !open ? t.multiSelect.all : t.multiSelect.placeholder
          }
          onChange={(event) => handleInputChange(event.target.value)}
          onFocus={handleInputFocus}
          onClick={handleInputClick}
          onKeyDown={handleKeyDown}
          className="block min-h-[3.25rem] w-full rounded-xl border px-4 py-3 pr-11 text-ink placeholder-ink-faint transition-colors focus:outline-none focus:ring-2 border-transparent bg-field focus:ring-field-focus disabled:cursor-not-allowed disabled:opacity-50"
        />
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-soft"
        />

        <div
          className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl bg-surface shadow-raised ring-1 ring-line"
          hidden={!open}
        >
          <ul
            id={listboxId}
            role="listbox"
            aria-multiselectable="true"
            aria-label={label}
            className={`max-h-72 overflow-auto${items.length > 0 ? " p-1" : ""}`}
          >
            {items.map((item, index) => {
              const selected = values.includes(item);
              const active = index === activeIndex;
              return (
                <li
                  key={item}
                  id={`${listboxId}-option-${index}`}
                  role="option"
                  aria-selected={selected}
                  onMouseDown={handleOptionMouseDown}
                  onClick={() => handleOptionClick(item)}
                  className={`flex min-h-tap cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-sm transition-colors ${
                    active ? "bg-accent-soft" : "bg-surface"
                  } text-ink`}
                >
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                    {selected ? (
                      <Check aria-hidden="true" className="h-4 w-4 text-accent" />
                    ) : null}
                  </span>
                  {item}
                </li>
              );
            })}
          </ul>
          {statusText !== "" && (
            <p
              aria-hidden="true"
              className={`${items.length > 0 ? "border-t border-line " : ""}px-4 py-2.5 text-sm ${statusClasses}`}
            >
              {statusText}
            </p>
          )}
        </div>
      </div>

      <p id={statusId} role="status" aria-live="polite" className="sr-only">
        {statusText}
      </p>

      {hint ? (
        <div id={hintId} className="mt-1.5 text-sm text-ink-soft">
          {hint}
        </div>
      ) : null}
    </div>
  );
}
