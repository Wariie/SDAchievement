// utils/logger.ts

/**
 * Centralized logging service for the SDAchievement plugin
 * Provides consistent logging with configurable levels and production-friendly output
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4
}

export interface LogConfig {
  level: LogLevel;
  prefix: string;
  enableTimestamp: boolean;
  enableStackTrace: boolean;
}

class Logger {
  private config: LogConfig;
  
  constructor() {
    // Default configuration - can be overridden
    this.config = {
      level: process.env.NODE_ENV === 'production' ? LogLevel.WARN : LogLevel.DEBUG,
      prefix: '[SDAchievement]',
      enableTimestamp: true,
      enableStackTrace: false
    };
  }

  configure(config: Partial<LogConfig>): void {
    this.config = { ...this.config, ...config };
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.config.level;
  }

  private formatMessage(level: string, message: string): string {
    const timestamp = this.config.enableTimestamp 
      ? `[${new Date().toISOString()}]` 
      : '';
    
    return `${timestamp} ${this.config.prefix} [${level}] ${message}`;
  }

  private logWithLevel(level: LogLevel, levelName: string, message: string, ...args: any[]): void {
    if (!this.shouldLog(level)) return;

    const formattedMessage = this.formatMessage(levelName, message);
    
    switch (level) {
      case LogLevel.DEBUG:
        console.debug(formattedMessage, ...args);
        break;
      case LogLevel.INFO:
        console.info(formattedMessage, ...args);
        break;
      case LogLevel.WARN:
        console.warn(formattedMessage, ...args);
        break;
      case LogLevel.ERROR:
        console.error(formattedMessage, ...args);
        if (this.config.enableStackTrace) {
          console.trace();
        }
        break;
    }
  }

  debug(message: string, ...args: any[]): void {
    this.logWithLevel(LogLevel.DEBUG, 'DEBUG', message, ...args);
  }

  info(message: string, ...args: any[]): void {
    this.logWithLevel(LogLevel.INFO, 'INFO', message, ...args);
  }

  warn(message: string, ...args: any[]): void {
    this.logWithLevel(LogLevel.WARN, 'WARN', message, ...args);
  }

  error(message: string, ...args: any[]): void {
    this.logWithLevel(LogLevel.ERROR, 'ERROR', message, ...args);
  }

  // Convenience methods for common use cases
  apiCall(endpoint: string, params?: any): void {
    this.debug(`API Call: ${endpoint}`, params);
  }

  apiResponse(endpoint: string, success: boolean, data?: any): void {
    if (success) {
      this.debug(`API Success: ${endpoint}`, data);
    } else {
      this.warn(`API Failed: ${endpoint}`, data);
    }
  }

  performanceStart(operation: string): void {
    this.debug(`Performance Start: ${operation}`);
  }

  performanceEnd(operation: string, duration: number): void {
    this.debug(`Performance End: ${operation} (${duration}ms)`);
  }

  userAction(action: string, data?: any): void {
    this.info(`User Action: ${action}`, data);
  }
}

// Export singleton instance
export const logger = new Logger();

// Export for testing/configuration
export { Logger };