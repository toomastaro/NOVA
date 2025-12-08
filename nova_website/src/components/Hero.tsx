import { Button } from "@/components/ui/button";
import { Send } from "lucide-react";

const Hero = () => {
  return (
    <section className="relative min-h-screen flex items-center justify-center pt-16 overflow-hidden">
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-transparent to-transparent" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-primary/10 rounded-full blur-3xl" />
      
      <div className="container mx-auto px-4 text-center relative z-10">
        <div className="animate-fade-in">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-4 py-2 text-sm text-muted-foreground mb-8">
            <span className="size-2 rounded-full bg-primary animate-pulse" />
            100+ админов за первые 24 часа
          </div>
        </div>

        <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-6 animate-slide-up" style={{ animationDelay: '0.1s' }}>
          Универсальный бот для{" "}
          <span className="text-primary">Telegram</span> каналов
        </h1>

        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-4 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          Все функции по одной цене. Посты, истории, рассылки, закупы, статистика и курс USDT — всего{" "}
          <span className="text-primary font-semibold">249₽</span> за канал в месяц
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center mt-8 animate-slide-up" style={{ animationDelay: '0.3s' }}>
          <Button variant="hero" asChild>
            <a href="https://t.me/novatg" target="_blank" rel="noopener noreferrer">
              <Send className="size-4" />
              Попробовать бесплатно
            </a>
          </Button>
          <Button variant="heroOutline" asChild>
            <a href="https://t.me/mousesquad" target="_blank" rel="noopener noreferrer">
              Связаться с поддержкой
            </a>
          </Button>
        </div>

        <p className="flex items-center justify-center gap-2 text-sm text-muted-foreground mt-6 animate-fade-in" style={{ animationDelay: '0.4s' }}>
          <span className="size-2 rounded-full bg-primary" />
          7 дней бесплатного периода
        </p>
      </div>
    </section>
  );
};

export default Hero;
