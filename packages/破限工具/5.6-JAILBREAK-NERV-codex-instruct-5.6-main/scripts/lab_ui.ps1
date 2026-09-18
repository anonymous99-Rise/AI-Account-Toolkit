param(
    [Parameter(Position = 0)]
    [ValidateSet('splash', 'progress')]
    [string]$Mode = 'splash',

    [Parameter(Position = 1)]
    [string]$Label = 'Loading function area',

    [Parameter(Position = 2)]
    [int]$Width = 42,

    [Parameter(Position = 3)]
    [int]$DelayMs = 45
)

try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
} catch {}

$Block = [char]0x2588
$Dot = [char]0x00B7
$Track = [char]0x2591
$Shade = [char]0x2591
$DoubleTopLeft = [char]0x2554
$DoubleTopRight = [char]0x2557
$DoubleBottomLeft = [char]0x255A
$DoubleBottomRight = [char]0x255D
$DoubleHorizontal = [char]0x2550
$DoubleVertical = [char]0x2551

$Glyphs = @{
    ' ' = @('00000', '00000', '00000', '00000', '00000')
    '5' = @('11111', '10000', '11110', '00001', '11110')
    '.' = @('00000', '00000', '00000', '00000', '00100')
    '6' = @('01110', '10000', '11110', '10001', '01110')
    '-' = @('00000', '00000', '11111', '00000', '00000')
    'J' = @('11111', '00010', '00010', '10010', '01100')
    'A' = @('01110', '10001', '11111', '10001', '10001')
    'I' = @('11111', '00100', '00100', '00100', '11111')
    'L' = @('10000', '10000', '10000', '10000', '11111')
    'B' = @('11110', '10001', '11110', '10001', '11110')
    'R' = @('11110', '10001', '11110', '10010', '10001')
    'E' = @('11111', '10000', '11110', '10000', '11111')
    'K' = @('10001', '10010', '11100', '10010', '10001')
    'N' = @('10001', '11001', '10101', '10011', '10001')
    'V' = @('10001', '10001', '10001', '01010', '00100')
}

function Convert-PatternLine {
    param([string]$Pattern)

    $line = $Pattern.Replace('1', $script:Block).Replace('0', ' ')
    return $line
}

function New-BlockLines {
    param([string]$Text)

    $rows = @('', '', '', '', '')
    foreach ($char in $Text.ToCharArray()) {
        $key = $char.ToString().ToUpperInvariant()
        $glyph = $Glyphs[$key]
        if (-not $glyph) {
            $glyph = $Glyphs[' ']
        }

        for ($i = 0; $i -lt 5; $i++) {
            $rows[$i] += (Convert-PatternLine $glyph[$i]) + '  '
        }
    }

    return $rows
}

function Convert-FigletLine {
    param([string]$Pattern)

    $line = $Pattern.Replace('#', $script:Block)
    $line = $line.Replace('.', $script:Shade)
    $line = $line.Replace('<', $script:DoubleTopLeft)
    $line = $line.Replace('>', $script:DoubleTopRight)
    $line = $line.Replace('[', $script:DoubleBottomLeft)
    $line = $line.Replace(']', $script:DoubleBottomRight)
    $line = $line.Replace('=', $script:DoubleHorizontal)
    $line = $line.Replace('|', $script:DoubleVertical)
    return $line
}

function Expand-FigletLines {
    param(
        [string[]]$Lines,
        [int]$ScaleX = 2,
        [int]$ScaleY = 2
    )

    $expanded = @()
    foreach ($line in $Lines) {
        $wide = New-Object System.Text.StringBuilder
        foreach ($char in $line.ToCharArray()) {
            for ($x = 0; $x -lt $ScaleX; $x++) {
                [void]$wide.Append($char)
            }
        }

        $wideLine = $wide.ToString()
        for ($y = 0; $y -lt $ScaleY; $y++) {
            $expanded += $wideLine
        }
    }

    return $expanded
}

function New-FigletLines {
    param([string]$Text)

    $glyphs = @{
        ' ' = @('    ', '    ', '    ', '    ', '    ', '    ')
        '5' = @('#######>', '##<====]', '#######>', '[====##|', '#######|', '[======]')
        '.' = @('   ', '   ', '   ', '   ', '##>', '[=]')
        '6' = @(' ######> ', '##<====] ', '#######> ', '##<==##>', '[######<]', ' [=====] ')
        '-' = @('      ', '      ', '#####>', '[====]', '      ', '      ')
        'J' = @('     ##>', '     ##|', '     ##|', '##   ##|', '[#####<]', ' [====] ')
        'A' = @(' #####> ', '##<==##>', '#######|', '##<==##|', '##|  ##|', '[=]  [=]')
        'I' = @('##>', '##|', '##|', '##|', '##|', '[=]')
        'L' = @('##>     ', '##|     ', '##|     ', '##|     ', '#######>', '[======]')
        'B' = @('######> ', '##<==##>', '######< ', '##<==##>', '######< ', '[=====] ')
        'R' = @('######> ', '##<==##>', '######< ', '##<==##>', '##|  ##|', '[=]  [=]')
        'E' = @('#######>', '##<====]', '#####>  ', '##<==]  ', '#######>', '[======]')
        'K' = @('##>  ##>', '##| ##<]', '#####<] ', '##<==##>', '##|  ##>', '[=]  [=]')
        'N' = @('###>   ##>', '####>  ##|', '##<##> ##|', '##|[##>##|', '##| [####|', '[=]  [===]')
        'V' = @('##>   ##>', '##|   ##|', '##|   ##|', '[##> ##<]', ' [####<] ', '  [==]   ')
    }

    $rows = @('', '', '', '', '', '')
    foreach ($char in $Text.ToCharArray()) {
        $key = $char.ToString().ToUpperInvariant()
        $glyph = $glyphs[$key]
        if (-not $glyph) {
            $glyph = $glyphs[' ']
        }

        for ($i = 0; $i -lt 6; $i++) {
            $rows[$i] += (Convert-FigletLine $glyph[$i]) + ' '
        }
    }

    return $rows
}

function Get-MaxLineLength {
    param([string[]]$Lines)

    $max = 0
    foreach ($line in $Lines) {
        if ($line.Length -gt $max) {
            $max = $line.Length
        }
    }

    return $max
}

function Join-BannerBlocks {
    param(
        [string[][]]$Blocks,
        [int]$Gap = 1
    )

    $joined = @()
    for ($blockIndex = 0; $blockIndex -lt $Blocks.Count; $blockIndex++) {
        if ($blockIndex -gt 0) {
            for ($g = 0; $g -lt $Gap; $g++) {
                $joined += ''
            }
        }
        $joined += $Blocks[$blockIndex]
    }

    return $joined
}

function Select-SplashBanner {
    param([int]$ConsoleWidth)

    $limit = [Math]::Max(40, $ConsoleWidth - 4)
    $full = New-FigletLines '5.6-JAILBREAK-NERV'
    $fullBig = Expand-FigletLines $full 1 2
    if ((Get-MaxLineLength $fullBig) -le $limit) {
        return $fullBig
    }
    if ((Get-MaxLineLength $full) -le $limit) {
        return $full
    }

    $splitFiglet = Join-BannerBlocks @((New-FigletLines '5.6-JAILBREAK'), (New-FigletLines '-NERV')) 1
    $splitFigletBig = Expand-FigletLines $splitFiglet 1 2
    if ((Get-MaxLineLength $splitFigletBig) -le $limit) {
        return $splitFigletBig
    }
    if ((Get-MaxLineLength $splitFiglet) -le $limit) {
        return $splitFiglet
    }

    $compact = Join-BannerBlocks @((New-BlockLines '5.6-JAILBREAK'), (New-BlockLines '-NERV')) 1
    $compactBig = Expand-FigletLines $compact 1 2
    if ((Get-MaxLineLength $compactBig) -le $limit) {
        return $compactBig
    }
    if ((Get-MaxLineLength $compact) -le $limit) {
        return $compact
    }

    return @('5.6-JAILBREAK-NERV')
}

function Write-Centered {
    param(
        [string[]]$Lines,
        [ConsoleColor]$Color
    )

    try {
        $consoleWidth = [Console]::WindowWidth
    } catch {
        $consoleWidth = 118
    }

    foreach ($line in $Lines) {
        $left = [Math]::Max(0, [Math]::Floor(($consoleWidth - $line.Length) / 2))
        Write-Host ((' ' * $left) + $line) -ForegroundColor $Color
    }
}

function Write-CornerTag {
    param([ConsoleColor]$Color)

    $tag = [string]$Dot + 'zxwn'
    try {
        $x = [Math]::Max(0, [Console]::WindowWidth - $tag.Length - 2)
        $y = [Math]::Max(0, [Console]::WindowHeight - 2)
        [Console]::SetCursorPosition($x, $y)
        Write-Host -NoNewline $tag -ForegroundColor $Color
    } catch {
        Write-Host (' ' * 86) -NoNewline
        Write-Host -NoNewline $tag -ForegroundColor $Color
    }
}

function Show-Splash {
    try {
        $consoleWidth = [Console]::WindowWidth
    } catch {
        $consoleWidth = 160
    }
    $banner = Select-SplashBanner $consoleWidth
    $frames = @(
        @{ Main = 'Cyan'; Accent = 'Magenta' },
        @{ Main = 'Magenta'; Accent = 'Cyan' },
        @{ Main = 'Blue'; Accent = 'White' },
        @{ Main = 'White'; Accent = 'DarkMagenta' },
        @{ Main = 'DarkCyan'; Accent = 'Magenta' },
        @{ Main = 'Cyan'; Accent = 'Blue' },
        @{ Main = 'Magenta'; Accent = 'White' }
    )

    try { [Console]::CursorVisible = $false } catch {}
    try {
        foreach ($frame in $frames) {
            $color = [ConsoleColor]::$($frame.Main)
            $accent = [ConsoleColor]::$($frame.Accent)
            Clear-Host
            Write-Host ''
            Write-Centered $banner $color
            Write-Host ''
            Write-Centered @('5.6-JAILBREAK-NERV') $accent
            Write-CornerTag $accent
            Start-Sleep -Milliseconds 310
            Clear-Host
            Start-Sleep -Milliseconds 110
        }
    } finally {
        try { [Console]::CursorVisible = $true } catch {}
    }
}

function Show-Progress {
    param(
        [string]$Text,
        [int]$BarWidth,
        [int]$Delay
    )

    $segments = @('DarkBlue', 'Blue', 'Cyan')
    $topLeft = [char]0x256D
    $topRight = [char]0x256E
    $bottomLeft = [char]0x2570
    $bottomRight = [char]0x256F
    $horizontal = [char]0x2500
    $vertical = [char]0x2502

    Write-Host ''
    Write-Host ('  ' + $Text) -ForegroundColor Cyan

    Write-Host -NoNewline '  '
    Write-Host -NoNewline $topLeft -ForegroundColor Blue
    for ($i = 1; $i -le $BarWidth; $i++) {
        Write-Host -NoNewline $horizontal -ForegroundColor Blue
    }
    Write-Host $topRight -ForegroundColor Blue

    Write-Host -NoNewline '  '
    Write-Host -NoNewline $vertical -ForegroundColor Blue

    $canUpdate = $true
    try {
        $barLeft = [Console]::CursorLeft
        $barTop = [Console]::CursorTop
    } catch {
        $canUpdate = $false
    }

    for ($i = 1; $i -le $BarWidth; $i++) {
        Write-Host -NoNewline $Track -ForegroundColor DarkBlue
    }
    Write-Host -NoNewline $vertical -ForegroundColor Blue
    Write-Host -NoNewline '  '
    try {
        $percentLeft = [Console]::CursorLeft
    } catch {
        $canUpdate = $false
    }
    Write-Host ('{0,3}%' -f 0)

    Write-Host -NoNewline '  '
    Write-Host -NoNewline $bottomLeft -ForegroundColor Blue
    for ($i = 1; $i -le $BarWidth; $i++) {
        Write-Host -NoNewline $horizontal -ForegroundColor Blue
    }
    Write-Host $bottomRight -ForegroundColor Blue

    if ($canUpdate) {
        try { [Console]::CursorVisible = $false } catch {}
        try {
            for ($i = 1; $i -le $BarWidth; $i++) {
                $part = [Math]::Min(2, [Math]::Floor(($i - 1) * 3 / $BarWidth))
                $percent = [Math]::Floor($i * 100 / $BarWidth)
                [Console]::SetCursorPosition($barLeft + $i - 1, $barTop)
                Write-Host -NoNewline $Block -ForegroundColor ([ConsoleColor]::$($segments[$part]))
                [Console]::SetCursorPosition($percentLeft, $barTop)
                Write-Host -NoNewline ('{0,3}%' -f $percent)
                Start-Sleep -Milliseconds $Delay
            }
            [Console]::SetCursorPosition(0, $barTop + 2)
        } finally {
            try { [Console]::CursorVisible = $true } catch {}
        }
    } else {
        Write-Host ('  ' + ('{0,3}%' -f 100))
    }
}

switch ($Mode) {
    'splash' { Show-Splash }
    'progress' { Show-Progress $Label $Width $DelayMs }
}
