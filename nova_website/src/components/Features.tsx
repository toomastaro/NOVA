import { FileText, Image, Send, ShoppingCart, MessageSquare, BarChart3, DollarSign } from "lucide-react";

const features = [
  {
    icon: FileText,
    title: "Посты",
    description: "Автоматическая публикация постов по расписанию с поддержкой всех форматов",
  },
  {
    icon: Image,
    title: "Истории",
    description: "Создание и публикация историй в вашем канале",
  },
  {
    icon: Send,
    title: "Рассылки",
    description: "Массовая рассылка сообщений подписчикам канала",
  },
  {
    icon: ShoppingCart,
    title: "Закупы",
    description: "Управление закупками рекламы в других каналах",
  },
  {
    icon: MessageSquare,
    title: "Бот приветки",
    description: "Автоматические приветственные сообщения для новых подписчиков",
  },
  {
    icon: BarChart3,
    title: "Статистика",
    description: "Детальная аналитика по всем вашим каналам",
  },
  {
    icon: DollarSign,
    title: "Курс USDT",
    description: "Актуальный курс USDT к рублю в режиме реального времени",
  },
];

const Features = () => {
  return (
    <section id="features" className="py-24 relative">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <p className="text-sm text-primary font-medium mb-2">Быстрый старт</p>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Все функции в одном пакете</h2>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Не нужно покупать отдельные функции. Получите полный набор инструментов для управления каналами
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {features.map((feature, index) => (
            <div
              key={feature.title}
              className="group rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:border-primary/50 hover:bg-card/80 hover:glow-primary"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="size-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                <feature.icon className="size-6 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Features;
