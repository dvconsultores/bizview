import { useT } from "../i18n";
import { ForbiddenMark, MessagePage } from "./NotFound";

export function Forbidden() {
  const t = useT();
  return <MessagePage mark={<ForbiddenMark />} title={t.errors.forbidden} text={t.errors.forbiddenText} />;
}
