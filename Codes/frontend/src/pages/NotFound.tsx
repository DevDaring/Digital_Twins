import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <p className="num text-6xl font-extrabold text-marigold-ink">404</p>
      <h1 className="mt-4 text-xl font-bold">{t("errors.notFound")}</h1>
      <Link to="/" className="btn-primary mt-6">
        {t("errors.goHome")}
      </Link>
    </div>
  );
}
