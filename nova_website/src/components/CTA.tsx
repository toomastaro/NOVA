import { Button } from "@/components/ui/button";
import { Send, Bell, MessageCircle } from "lucide-react";

const ctaItems = [
  {
    icon: Send,
    title: "Бот NovaTG",
    description: "Начните использовать бот прямо сейчас",
    link: "https://t.me/novatg",
    buttonText: "Открыть бот",
  },
  {
    icon: Bell,
    title: "Новости",
    description: "Следите за обновлениями сервиса",
    link: "https://t.me/NewsNova",
    buttonText: "Подписаться",
  },
  {
    icon: MessageCircle,
    title: "Поддержка",
    description: "Получите помощь от нашей команды",
    link: "https://t.me/mousesquad",
    buttonText: "Написать",
  },
];

const CTA = () => {
  return (
    <section className="py-24 relative border-t border-border">
      <div className="absolute inset-0 bg-gradient-to-t from-primary/5 via-transparent to-transparent" />
      <div className="container mx-auto px-4 relative z-10">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Готовы начать?</h2>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Присоединяйтесь к сотням администраторов, которые уже используют NovaTG для управления своими каналами
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
          {ctaItems.map((item) => (
            <div
              key={item.title}
              className="rounded-xl border border-border bg-card p-6 text-center hover:border-primary/50 transition-colors"
            >
              <div className="size-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                <item.icon className="size-6 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">{item.title}</h3>
              <p className="text-sm text-muted-foreground mb-4">{item.description}</p>
              <Button variant="outline" size="sm" asChild className="w-full">
                <a href={item.link} target="_blank" rel="noopener noreferrer">
                  {item.buttonText}
                </a>
              </Button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default CTA;
