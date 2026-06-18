import { NavLink, Outlet } from "react-router-dom";
import { FileText, Lightbulb, Activity } from "lucide-react";

const navItems = [
  { to: "/logs", icon: FileText, label: "日志分析" },
  { to: "/optimize", icon: Lightbulb, label: "智能优化" },
];

export default function Layout() {
  return (
    <div className="flex h-screen">
      {/* 侧边栏 */}
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="p-5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Activity className="w-6 h-6 text-indigo-600" />
            <div>
              <h1 className="text-base font-bold text-gray-900">智能体管理</h1>
              <p className="text-xs text-gray-400">云顶新耀</p>
            </div>
          </div>
        </div>

        {/* 导航 */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`
              }
            >
              <Icon className="w-4.5 h-4.5" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* 底部 */}
        <div className="p-4 border-t border-gray-100">
          <p className="text-xs text-gray-400 text-center">
            管理后端 v0.1.0
          </p>
        </div>
      </aside>

      {/* 主内容 */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
