const Footer = () => {
  return (
    <footer className="py-8 border-t border-border">
      <div className="container mx-auto px-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <a href="#" className="flex items-center gap-1 text-xl font-bold">
            <span className="text-foreground">N</span>
            <span className="text-primary">☐</span>
            <span className="text-foreground">VA</span>
          </a>

          <div className="flex flex-col sm:flex-row items-center gap-4 text-sm text-muted-foreground">
            <a
              href="https://telegra.ph/NovaTG---Polzovatelskoe-soglashenie-12-05"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Пользовательское соглашение
            </a>
            <span className="hidden sm:inline">•</span>
            <a
              href="https://telegra.ph/NovaTG---Politika-konfidencialnosti-12-05"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Политика конфиденциальности
            </a>
          </div>

          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} NovaTG
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
