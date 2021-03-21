#%%
def paintLineOn(buff, text, indent):
    buff += indent + text + "\n"
    return buff

def paint_type(typeName):
    # handle combos
    # TODO
    if typeName.value == "TypeExpr":
        op, left, right = typeName.children
        left, right = paint_type(left), paint_type(right)
        op = op.value
        left, right = (left, right) if "mut" in left else (right, left)
        if op == "*" :
            return left + " " + right

    if typeName.value == "ID":
        name = typeName.children[0].value
        if name == "Int":
            return "i32"
        if name == "String":
            return "string"
        if name == "Mut":
            return "mut"
        if name == "Obj":
            return "HashMap<&str, Box<dyn Any + 'static>>"
        return name

def paint_call(name, arg):
    argText = paint_expression(arg)
    if name == "print":
        return 'println!("{:#?}", ' + argText + ")"
    return f"{name}({argText})"


def paint_expression(expr, currentIndent=""):

    if expr.value == "String" or expr.value == "Number":
        return expr.children[0].value
    if expr.value == "ID":
        return expr.children[0].value
    if expr.value == "BinOp":
        # TODO handle Glace-specific ops
        op, left, right = expr.children
        # Single Access
        if right.value == "TypedDecl" and op.value == "'":
            left = paint_expression(left, currentIndent)
            vartype, varname = right.children
            vartype = paint_type(vartype)
            return f'{left}.get("{varname[1][0][0]}").unwrap().downcast_ref::<{vartype}>().unwrap()'
        # Multiple access
        if right.value == "BinOp" and op.value == "'":
            out = paint_expression(left, currentIndent)
            while right.value == "BinOp":
                op, left, right = right.children
                if op.value != "'":
                    raise NotImplementedError(f"Binary Operation ({op.value}) on Object get")
                vartype, varname = left.children
                vartype = paint_type(vartype)
                out += f'.get("{varname[1][0][0]}").unwrap().downcast_ref::<{vartype}>().unwrap()'
            vartype, varname = right.children
            vartype = paint_type(vartype)    
            out += f'.get("{varname[1][0][0]}").unwrap().downcast_ref::<{vartype}>().unwrap()'
            return out
        left, right = paint_expression(left, currentIndent), paint_expression(right, currentIndent)
        return f"{left} {op.value} {right}"
    if expr.value == "Call":
        iden, arg = expr.children
        if iden.value == "ID":
            name = iden[1][0][0]
            return paint_call(name, arg)
    if expr.value == "ComplexCall":
        out = ""
        iden, *extra = expr.children
        out += iden[1][0][0]
        for call in extra:
            if call.value == "Parg":
                out += "(" + paint_expression(call.children[0], currentIndent) + ")"
            if call.value == "Dcol":
                out += "::" + call[1][0][1][0][0]
            if call.value == "Dot":
                out += "." + call[1][0][1][0][0]
        return out

    # Reworking this
    if expr.value == "Object":
        assigns = expr.children
        out = "{\n" + currentIndent + "\t" + "let mut object: HashMap<&str, Box<dyn Any + 'static>> = HashMap::new();" + "\n"
        for assign in assigns:
            name, value = assign.children
            if name.value == "ID":
                name = name[1][0][0]
            value = paint_expression(value, currentIndent+"\t")
            out += currentIndent + "\t" + f'object.insert("{name}", Box::new({value}));' + "\n"

        return out + currentIndent + "\t" + "object" + "\n" + currentIndent + "}"

    if expr.value == "TypedDecl":
        vartype, varname = expr.children

    if expr.value == "Function":
        default = paint_function("§§", expr, currentIndent)
        return default.split("§§")[1][3:-2].replace("\n", "\n" + currentIndent + "\t")
    
    if expr.value == "Block":
        prg = paint_program(expr.children, currentIndent+"\t")
        return "{\n" + prg + currentIndent + "}"

    return "exprNotImplemented"

def paint_function(name, tree, currentIndent=""):
    argument, body = tree.children

    # Normal function
    if body.value == "FunctionBody":
        argsText = ""
        # TODO rework the multi-arg logic
        if argument.value != "None":
            argument = argument.children[0]
            if argument.value == "TypedDecl":
                argName, type = argument[1][1][1][0][0], paint_type(argument.children[0])
                argsText = f"{argName}: {type}"

        retType, retValue = body.children
        outputType = paint_type(retType)

        bodyText = ""
        if retValue.value == "Block":
            bodyText = paint_program(retValue.children, currentIndent+"\t")
        else:
            bodyText = currentIndent + "\t" + str(paint_expression(retValue, currentIndent)) + "\n"

        outputText = f" -> {outputType}" if outputType != "Void" else ""

        return f"fn {name}({argsText}){outputText} " + "{" + f"\n{bodyText}{currentIndent}" + "}\n"
    # Lambda
    else:
        argsText = ""
        # TODO same rework as above
        if argument.value != "None":
            if argument.children[0][1][0].value != "ID":
                argsText = argument.children[0][1][0].value
            else:
                argName = argument.children[0][1][1][1][0][0]
                type    = paint_type(argument.children[0][1][0])
                argsText = f"{argName} : {type}"
        bodyText = compl = ""
        if body.value == "Block":
            bodyText = "{\n" + paint_program(body.children, currentIndent+"\t") + currentIndent + "}"
        else:
            bodyText = str(paint_expression(body, currentIndent))
            if bodyText[0] == '|':
                compl = " move"
                newBody = ""
                for i, e in enumerate(bodyText.splitlines()):
                    if i == 0:
                        newBody += e
                    else:
                        extraTab = "\t" if i != len(bodyText.splitlines())-1 else ""
                        newBody += "\n" + currentIndent + extraTab + e.strip()
                bodyText = newBody
        return f"let {name} = |{argsText}|{compl} {bodyText};" + "\n"



#%%
def paint_program(instructions, currentIndent=""):

    out = ""
    for instr in instructions:
        name, extra = instr

        if name == "If":
            expr, block = extra
            expr, block = paint_expression(expr, currentIndent), paint_program(block.children, currentIndent+"\t")
            out = paintLineOn(out, f"if {expr} " + "{\n" + block + currentIndent +  "}", currentIndent)
        if name == "For":
            expr, block = extra
            expr, block = paint_expression(expr, currentIndent), paint_program(block.children, currentIndent+"\t")
            out = paintLineOn(out, f"for {expr} " + "{\n" + block + currentIndent +  "}", currentIndent)

        if name == "TVDecl":
            vartype, iden, value = extra
            varname = iden.children[0].value
            typeText = paint_type(vartype)
            varvalue = paint_expression(value, currentIndent)
            mods = None
            if "mut" in typeText:
                mods = "mut"
                typeText = typeText.replace("mut ", "")
            out = paintLineOn(out, f"let {mods}{' ' if mods!=None else ''}{varname}: {typeText} = {varvalue};", currentIndent)

        if name == "AutoDecl":
            iden, value = extra
            varname = iden.children[0].value
            if value.value == "Function": # declare a function
                functext = paint_function(varname, value, currentIndent)
                out += currentIndent + functext
            else: # use the let keyword without any typing concerns
                varvalue = paint_expression(value, currentIndent)
                out = paintLineOn(out, f"let {varname} = {varvalue};", currentIndent)
        if name == "Reassign":
            iden, value = extra
            varname = iden.children[0].value
            varvalue = paint_expression(value)
            out = paintLineOn(out, f"{varname} = {varvalue};", currentIndent)


        if name == "Call":
            iden, arg = extra
            if iden.value == "ID":
                name = iden.children[0].value
                calltext = paint_call(name, arg)
                out = paintLineOn(out, f"{calltext};", currentIndent)
        if name == "ComplexCall":
            val = paint_expression(instr, currentIndent)
            out = paintLineOn(out, val + ";", currentIndent)

        if name == "Ret":
            expr = extra[0]
            exprText = paint_expression(expr, currentIndent)
            out = paintLineOn(out, f"{exprText}", currentIndent)
        if name == "Return":
            expr = extra[0]
            exprText = paint_expression(expr, currentIndent)
            out = paintLineOn(out, f"return {exprText};", currentIndent)

        if currentIndent == "":
            out += "\n"

    return out

def paint_total(instructions):
    return """
use std::collections::HashMap;
use std::any::Any;

""" + paint_program(instructions)


# %%
