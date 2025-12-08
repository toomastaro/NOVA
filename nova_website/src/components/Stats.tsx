const Stats = () => {
  return (
    <section className="py-24 relative border-y border-border">
      <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-primary/5" />
      <div className="container mx-auto px-4 relative z-10">
        <div className="text-center mb-12">
          <p className="text-sm text-primary font-medium mb-2">Быстрый старт</p>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Новый сервис с впечатляющим стартом</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            За первые сутки после запуска более 100 администраторов начали использовать NovaTG для своих проектов
          </p>
        </div>
      </div>
    </section>
  );
};

export default Stats;
