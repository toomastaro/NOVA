import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";

const features = [
  "Все 7 функций включены",
  "Неограниченное количество постов",
  "Приоритетная поддержка",
  "Регулярные обновления",
  "Без скрытых платежей",
];

const Pricing = () => {
  return (
    <section id="pricing" className="py-24 relative">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Честная цена без переплат</h2>
          <p className="text-muted-foreground">
            В 3-5 раз дешевле конкурентов. Одна цена на все функции
          </p>
        </div>

        <div className="max-w-md mx-auto">
          <div className="relative rounded-2xl border border-primary/50 bg-card p-8 glow-primary">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <span className="bg-primary text-primary-foreground text-xs font-semibold px-3 py-1 rounded-full">
                Популярный выбор
              </span>
            </div>

            <div className="text-center mb-8">
              <h3 className="text-xl font-semibold mb-4">Единый пакет</h3>
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-5xl font-bold text-primary">249₽</span>
                <span className="text-muted-foreground">/месяц</span>
              </div>
              <p className="text-sm text-muted-foreground mt-2">за один канал</p>
            </div>

            <ul className="space-y-4 mb-8">
              {features.map((feature) => (
                <li key={feature} className="flex items-center gap-3">
                  <div className="size-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                    <Check className="size-3 text-primary" />
                  </div>
                  <span className="text-sm">{feature}</span>
                </li>
              ))}
            </ul>

            <div className="space-y-3">
              <div className="rounded-lg bg-primary/10 p-4 text-center">
                <p className="text-sm font-medium text-primary">7 дней бесплатно</p>
                <p className="text-xs text-muted-foreground mt-1">Попробуйте все функции без оплаты</p>
              </div>
              <Button className="w-full" size="lg" asChild>
                <a href="https://t.me/novatg" target="_blank" rel="noopener noreferrer">
                  Начать бесплатный период
                </a>
              </Button>
            </div>
          </div>

          <div className="mt-6 text-center">
            <p className="text-sm text-muted-foreground mb-2">Для админов с сетками по 12+ каналов</p>
            <a
              href="https://t.me/mousesquad"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline"
            >
              Индивидуальные условия →
            </a>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Pricing;
