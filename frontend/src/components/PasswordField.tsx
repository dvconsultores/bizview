import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useState } from "react";
import { useT } from "../i18n";
import { Input, type InputProps } from "./Input";

export const PasswordField = forwardRef<HTMLInputElement, Omit<InputProps, "type" | "trailing">>(
  function PasswordField(props, ref) {
    const t = useT();
    const [visible, setVisible] = useState(false);
    return (
      <Input
        ref={ref}
        type={visible ? "text" : "password"}
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        trailing={
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl text-ink-soft hover:text-accent"
            aria-label={visible ? t.common.hide : t.common.show}
            aria-pressed={visible}
          >
            {visible ? <EyeOff className="h-5 w-5" aria-hidden /> : <Eye className="h-5 w-5" aria-hidden />}
          </button>
        }
        {...props}
      />
    );
  },
);
