import { Card, CardContent, CardHeader } from "@/components/ui/card";

interface HeadlineCardProps {
  sourceName: string;
  headlines: string[];
  totalArticles?: number;
}

export function HeadlineCard({
  sourceName,
  headlines,
  totalArticles,
}: HeadlineCardProps) {
  const displayHeadlines = headlines.slice(0, 3);
  const remaining = (totalArticles ?? headlines.length) - displayHeadlines.length;

  return (
    <Card className="border-rule-gray bg-white">
      <CardHeader className="pb-2">
        <h3 className="font-body text-xs font-semibold uppercase tracking-wider text-caption">
          {sourceName}
        </h3>
      </CardHeader>
      <CardContent className="pt-0">
        <ul className="space-y-2">
          {displayHeadlines.map((headline, i) => (
            <li key={i} className="font-headline text-sm font-bold text-ink">
              {headline}
            </li>
          ))}
        </ul>
        {remaining > 0 && (
          <p className="mt-2 font-body text-xs text-caption">
            + {remaining} more article{remaining === 1 ? "" : "s"}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
