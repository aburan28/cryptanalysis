-- Make long inline code (hashes, paths) breakable in the pdflatex report.
function Code(el)
  if FORMAT:match("latex") and #el.text > 28 then
    local t = el.text:gsub("([\\{}_#%%&$^~])", function(c)
      local map = {["\\"]="\\textbackslash{}", ["{"]="\\{", ["}"]="\\}", ["_"]="\\_",
                   ["#"]="\\#", ["%"]="\\%", ["&"]="\\&", ["$"]="\\$",
                   ["^"]="\\textasciicircum{}", ["~"]="\\textasciitilde{}"}
      return map[c]
    end)
    return pandoc.RawInline("latex", "\\texttt{\\seqsplit{" .. t .. "}}")
  end
end
